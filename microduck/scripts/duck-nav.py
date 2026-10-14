#!/usr/bin/env python3
"""Walk a duck to a goal on its own, around whatever the ToF sees in the way, and stop there.

    scripts/duck-nav.py 2.0 0.0              # the point 2 m ahead of where the duck stands now
    scripts/duck-nav.py 1.5 0.5 --yaw 90     # 1.5 m ahead, 0.5 m left, and end facing left
    DUCK_SIM_SCENE=obstacles scripts/duck-sim && scripts/duck-nav.py --absolute 2 0   # onto the course's red disc

The goal is in the frame the duck stands in when this starts: x forward, y left, metres — or, with
`--absolute`, in the odometry frame, which in duck-sim is the scene's. The difference matters: a duck
that rises from sitting ends up facing 5-15 degrees off the course's axis, so "2 m ahead" from where
it stands is half a metre beside a marker 2 m down the course. Nothing
here knows about a simulator — it is a client of `robotd` and `tofd` like `robotctl`, over the same
two sockets, so it drives a robot on a desk the same way. Standard library only, for that reason.

**What it uses.** `robot.state` carries contact odometry (`odom`: where the trunk is and which way it
faces), the trunk IMU's orientation, and the ToF's pose in the trunk frame from the head FK; the
beam directions come from `robot.model`. Each depth zone is put in the odometry frame with those,
returns near the floor are dropped, and what is left goes into a short-lived grid of occupied cells,
so a box that has left the 45-degree cone as the duck turns past it is still remembered.

**How it steers.** Every tick it scores candidate headings around the bearing to the goal and picks
the one closest to that bearing whose corridor (the duck's width plus a margin) is free for as far as
it needs to look. Turning is proportional to the heading error; forward speed falls off with it and
with the distance left, so the duck slows into the goal instead of overshooting. Inside the
tolerance it stops, turns to `--yaw` if one was asked for, and sends zeros — `robotd` hands the robot
back to the standing policy on its own once the twist is zero.

**What it is not.** Odometry drifts: "stopped at the goal" means where odometry believes the goal
is. And the walking policy only tracks a velocity — it does not step over anything, so obstacles are
gone around, never climbed.
"""

import argparse
import itertools
import json
import math
import os
import socket
import sys
import threading
import time

STATE = os.path.expanduser(os.environ.get("DUCK_SIM_STATE", "~/.cache/duck-sim"))

# The walking policy trains on |vx| <= 0.4, |vy| <= 0.3, |vyaw| <= 1.0; stay well inside it.
MAX_VX = 0.20
MAX_VYAW = 0.8
# Below these a policy marks time: it steps on the spot rather than going anywhere, and a duck
# stepping on the spot is what contact odometry drifts on — 13 cm in 15 s of it, measured against the
# simulator's ground truth, where 2 m of real walking cost 5. So the duck walks or turns, never dawdles.
MIN_VX = 0.10
MIN_VYAW = 0.30
APPROACH = 0.30    # inside this the duck closes in forward or backward, whichever faces the goal
RATE_HZ = 10  # `robotd` drops an intent 500 ms after the last one, so resend well inside that

# After a fall `robotd` goes limp, poses and stands the duck back up on its own; with `--retries`
# the run carries on once the trunk has been upright this long.
UPRIGHT_GZ = -0.95
UPRIGHT_S = 1.5
RECOVER_TIMEOUT = 20.0

HALF_WIDTH = 0.10  # half the duck's footprint, metres
MARGIN = 0.08      # clearance kept on each side of the planning corridor
LOOKAHEAD = 0.8    # how far ahead a heading has to be free
STOP_AHEAD = 0.20  # something this close in the duck's own width stops forward motion

CELL = 0.05        # obstacle grid, metres
SEEN = 2           # frames that must land in a cell before it counts: one noisy return is not a box
FORGET_S = 20.0    # a cell not seen again for this long is dropped
MIN_RANGE = 0.10   # the sensor's short-range noise band, as `kinematics::tof` has it
MAX_RANGE = 1.2    # further than this is not worth steering around yet
# A return lower than this above the ground is the floor. It grows with range because the error does:
# the ToF frame and the state it is paired with are up to a tick apart, and a trunk pitching while it
# walks turns that into centimetres of height a metre out — enough to ink the floor as an obstacle.
FLOOR_Z = 0.03
FLOOR_Z_PER_M = 0.04
CEILING_Z = 0.40   # higher than this the duck walks under it
STATUS_VALID = (5, 9)


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def rotate(q, v):
    """`v` rotated by the scalar-first unit quaternion `q`."""
    w, x, y, z = q
    vx, vy, vz = v
    # t = 2 * (q.xyz × v); v' = v + w t + q.xyz × t
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


class Link:
    """One JSON-RPC connection: calls answered by id, the latest notification of each method kept."""

    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(path)
        self.out = self.sock.makefile("w")
        self.ids = itertools.count(1)
        self.lock = threading.Lock()
        self.answers = {}
        self.latest = {}
        self.arrived = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.sock.makefile("r"):
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            with self.arrived:
                if "id" in msg and msg.get("id") is not None:
                    self.answers[msg["id"]] = msg
                elif "method" in msg:
                    self.latest[msg["method"]] = msg.get("params")
                self.arrived.notify_all()
        with self.arrived:
            self.latest["closed"] = True
            self.arrived.notify_all()

    def send(self, method, params=None, id=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if id is not None:
            msg["id"] = id
        with self.lock:
            self.out.write(json.dumps(msg) + "\n")
            self.out.flush()

    def call(self, method, params=None, timeout=5.0):
        id = next(self.ids)
        self.send(method, params, id)
        deadline = time.monotonic() + timeout
        with self.arrived:
            while id not in self.answers:
                left = deadline - time.monotonic()
                if left <= 0 or self.latest.get("closed"):
                    raise SystemExit(f"{method}: no answer")
                self.arrived.wait(left)
            answer = self.answers.pop(id)
        if "error" in answer:
            raise SystemExit(f"{method}: {answer['error'].get('message')}")
        return answer.get("result")

    def wait_for(self, method, timeout=5.0):
        deadline = time.monotonic() + timeout
        with self.arrived:
            while method not in self.latest:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self.arrived.wait(left)
            return self.latest[method]


class Obstacles:
    """Cells in the odometry frame that returns have landed in: how many frames, and when last."""

    def __init__(self, step_over=FLOOR_Z):
        self.hits = {}
        self.cells = {}  # the ones seen often enough to steer around
        self.last_seq = None
        # Anything lower than this above the ground is something the gait walks over — the floor,
        # a threshold, a step — rather than something to steer around. A gait that cannot climb
        # trips on what it is told to ignore, so this says what the LOADED policy can climb.
        self.step_over = step_over

    def add(self, frame, state, beams):
        if frame is None or frame.get("seq") == self.last_seq:
            return
        self.last_seq = frame.get("seq")
        tof = (state.get("frames") or {}).get("tof")
        imu = state.get("imu")
        if not tof or not imu:
            return
        odom = state["odom"]
        now = time.monotonic()
        landed = set()
        for zone, (mm, status) in enumerate(zip(frame["distance_mm"], frame["status"])):
            r = mm / 1000.0
            if status not in STATUS_VALID or not MIN_RANGE <= r <= MAX_RANGE:
                continue
            ray = rotate(tof["quat"], tuple(r * c for c in beams[zone]))
            in_trunk = tuple(p + d for p, d in zip(tof["pos"], ray))
            offset = rotate(imu["quat"], in_trunk)
            z = odom["position"][2] + offset[2]
            if not self.step_over + FLOOR_Z_PER_M * r < z < CEILING_Z:
                continue
            x = odom["position"][0] + offset[0]
            y = odom["position"][1] + offset[1]
            landed.add((round(x / CELL), round(y / CELL)))
        for key in landed:
            count, _ = self.hits.get(key, (0, now))
            self.hits[key] = (count + 1, now)
            if count + 1 >= SEEN:
                self.cells[key] = now
        for key in [k for k, (_, t) in self.hits.items() if now - t > FORGET_S]:
            del self.hits[key]
            self.cells.pop(key, None)

    def free_distance(self, x, y, heading, reach, half=HALF_WIDTH + MARGIN):
        """How far a corridor from (x, y) along `heading` runs before something is in it."""
        c, s = math.cos(heading), math.sin(heading)
        nearest = reach
        for cx, cy in self.cells:
            dx, dy = cx * CELL - x, cy * CELL - y
            ahead = dx * c + dy * s
            if 0.0 < ahead < nearest and abs(-dx * s + dy * c) < half:
                nearest = ahead
        return nearest


def choose_heading(obstacles, x, y, bearing, reach, side):
    """The free heading closest to the bearing, and which side of the bearing it is on.

    `side` is the way the duck is already going round something: +1 left, -1 right, 0 when it is
    not detouring. Going round the other way costs extra, so the duck commits to one side of a box
    instead of dithering between two gaps that score the same — dithering is turning in place, and
    turning in place is where contact odometry slips most. Nothing free for the whole reach: the
    most open heading, still preferring the committed side, and `free` says so."""
    candidates = []
    for k in range(-14, 15):
        h = wrap(bearing + math.radians(7.5 * k))
        candidates.append((k, h, obstacles.free_distance(x, y, h, reach)))

    def switching(k):
        return side != 0 and k != 0 and (k > 0) != (side > 0)

    clear = [(abs(k) + (6 if switching(k) else 0), k, h) for k, h, d in candidates if d >= reach - 1e-6]
    if clear:
        _, k, h = min(clear)
        return h, True, (k > 0) - (k < 0)
    _, k, h = max((d - 0.02 * abs(k) - (0.3 if switching(k) else 0.0), k, h) for k, h, d in candidates)
    return h, False, side or (k > 0) - (k < 0)


def main():
    global MAX_VX, MIN_VX
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("x", type=float, help="goal, metres forward of where the duck stands now")
    ap.add_argument("y", type=float, help="goal, metres to its left")
    ap.add_argument("--yaw", type=float, default=None, help="final heading, degrees left of the start heading")
    ap.add_argument("--absolute", action="store_true",
                    help="x, y and --yaw are in the odometry frame, not the start pose. In duck-sim that is "
                         "the scene's own frame (the obstacle course's red disc is at 2 0); on a robot it is "
                         "wherever the robot booted, facing whichever way it faced")
    ap.add_argument("--tolerance", type=float, default=0.05, help="how close counts as there, metres")
    ap.add_argument("--timeout", type=float, default=120.0, help="give up after this many seconds")
    ap.add_argument("--socket", default=os.path.join(STATE, "duck.sock"), help="robotd's socket")
    ap.add_argument("--tof", default=None, help="tofd's socket (default: beside robotd's, as duck-sim lays them out)")
    ap.add_argument("--speed", type=float, default=0.20,
                    help="top forward speed, m/s (default %(default)s). Raise it for a gait with a "
                         "deadband: the rough policy stands still below about 0.25, so --speed 0.3 is "
                         "what makes it walk at all. The floor under which it marks time scales with it")
    ap.add_argument("--step-over", type=float, default=FLOOR_Z,
                    help="metres of rise the loaded gait can walk over instead of around (default %(default)s). "
                         "On the duck-sim steps course, --step-over 0.08 puts the whole flight under the line, so "
                         "the duck walks up it; leave it at the default for a gait that cannot climb")
    ap.add_argument("--retries", type=int, default=0,
                    help="falls to wait out and carry on after — robotd stands the duck back up on its own "
                         "when limp_fall is on — before giving up (default %(default)s: stop at the first)")
    ap.add_argument("--log", default=None, help="write the run as JSON lines: the goal, every tick, the obstacle cells")
    args = ap.parse_args()
    MAX_VX = args.speed
    MIN_VX = max(0.10, 0.6 * args.speed)
    log = open(args.log, "w") if args.log else None

    tof_path = args.tof or os.path.realpath(args.socket).replace(".sock", "-tof.sock")
    robot = Link(args.socket)
    beams = robot.call("robot.model")["tof_beams"]
    robot.call("robot.subscribe", {"hz": 20})
    state = robot.wait_for("robot.state")
    if state is None:
        raise SystemExit("robotd is not streaming state")
    if state["safety"]["fallen"]:
        raise SystemExit("the duck is down — stand it up first")

    try:
        tof = Link(tof_path)
        tof.call("tof.stream")
    except OSError as e:
        print(f"no ToF at {tof_path} ({e}) — driving blind", file=sys.stderr)
        tof = None

    x0, y0, _ = state["odom"]["position"]
    yaw0 = state["odom"]["yaw"]
    if args.absolute:
        # Report the error along the odometry frame's own axes, as the goal was given.
        gx, gy, frame_yaw = args.x, args.y, 0.0
    else:
        gx = x0 + args.x * math.cos(yaw0) - args.y * math.sin(yaw0)
        gy = y0 + args.x * math.sin(yaw0) + args.y * math.cos(yaw0)
        frame_yaw = yaw0
    goal_yaw = wrap(frame_yaw + math.radians(args.yaw)) if args.yaw is not None else None
    print(f"goal: {math.hypot(gx - x0, gy - y0):.2f} m away" + (f", ending at {args.yaw:.0f} deg" if goal_yaw is not None else ""))
    if log:
        log.write(json.dumps({"start": [x0, y0, yaw0], "goal": [gx, gy, goal_yaw]}) + "\n")

    obstacles = Obstacles(step_over=args.step_over)
    side = 0
    started = time.monotonic()
    last_print = 0.0
    phase = "walk"
    falls = 0

    def move(vx, vyaw):
        robot.send("robot.move", {"vx": vx, "vy": 0.0, "vyaw": vyaw})

    def recover():
        """Hold still while `robotd` gets the duck back up; False if it never does."""
        upright_since = None
        deadline = time.monotonic() + RECOVER_TIMEOUT
        while time.monotonic() < deadline:
            move(0.0, 0.0)
            s = robot.latest["robot.state"]
            up = not s["safety"]["fallen"] and not s["safety"]["limp"] and s["safety"]["gravity"][2] < UPRIGHT_GZ
            if not up:
                upright_since = None
            elif upright_since is None:
                upright_since = time.monotonic()
            elif time.monotonic() - upright_since > UPRIGHT_S:
                return True
            time.sleep(1.0 / RATE_HZ)
        return False

    try:
        while True:
            tick = time.monotonic()
            state = robot.latest["robot.state"]
            if state["safety"]["fallen"] or state["safety"]["limp"]:
                if falls >= args.retries:
                    raise SystemExit("the duck fell — stopping")
                falls += 1
                print(f"{tick - started:5.1f}s  fell ({falls} of {args.retries}) — waiting for it to get up")
                if not recover():
                    raise SystemExit("the duck fell and did not get up — stopping")
                side = 0
                continue
            if tick - started > args.timeout:
                raise SystemExit("timed out before reaching the goal")
            if tof is not None:
                obstacles.add(tof.latest.get("tof.frame"), state, beams)

            x, y, _ = state["odom"]["position"]
            yaw = state["odom"]["yaw"]
            dist = math.hypot(gx - x, gy - y)

            if phase == "walk" and dist < args.tolerance:
                phase = "turn" if goal_yaw is not None else "done"
            if phase == "turn" and abs(wrap(goal_yaw - yaw)) < math.radians(5):
                phase = "done"

            if phase == "done":
                break
            bearing = math.atan2(gy - y, gx - x)
            if phase == "turn":
                err = wrap(goal_yaw - yaw)
                vx, note = 0.0, "turning to the final heading"
            elif dist < APPROACH:
                # Close in along the line to the goal, backing up if it is behind: overshooting by a
                # few centimetres then costs a step back, not a turn on the spot.
                ahead = math.cos(wrap(bearing - yaw)) >= 0.0
                err = wrap((bearing if ahead else bearing + math.pi) - yaw)
                speed = min(MAX_VX, 0.5 * dist + MIN_VX)
                vx = (speed if ahead else -speed) if abs(err) < math.radians(45) else 0.0
                if ahead and obstacles.free_distance(x, y, yaw, STOP_AHEAD, HALF_WIDTH) < STOP_AHEAD:
                    vx = 0.0
                note = "closing in" if ahead else "closing in, backing up"
            else:
                reach = min(LOOKAHEAD, dist + 0.05)
                heading, free, side = choose_heading(obstacles, x, y, bearing, reach, side)
                err = wrap(heading - yaw)
                vx = MAX_VX * math.cos(err) ** 2 if abs(err) < math.radians(60) else 0.0
                # When nothing is clear for the whole reach, creep toward the most open heading
                # rather than turn on the spot, slowing as whatever is in it gets close.
                room = obstacles.free_distance(x, y, heading, reach)
                if room < reach - 1e-6:
                    vx = min(vx, MAX_VX * max(0.0, (room - STOP_AHEAD) / 0.3))
                if vx > 0.0:
                    vx = max(vx, MIN_VX)
                if obstacles.free_distance(x, y, yaw, STOP_AHEAD, HALF_WIDTH) < STOP_AHEAD:
                    vx = 0.0
                detour = math.degrees(wrap(heading - bearing))
                note = "blocked, turning in place" if not free else (f"detour {detour:+.0f} deg" if abs(detour) > 1 else "straight at it")
            vyaw = max(-MAX_VYAW, min(MAX_VYAW, 1.5 * err))
            if vx == 0.0 and abs(err) > math.radians(3):
                vyaw = math.copysign(max(abs(vyaw), MIN_VYAW), vyaw)  # a turn that turns, not a shuffle
            move(vx, vyaw)
            if log:
                log.write(json.dumps({"t": round(tick - started, 2), "x": x, "y": y, "yaw": yaw,
                                      "vx": vx, "vyaw": vyaw, "note": note}) + "\n")

            if tick - last_print > 0.5:
                last_print = tick
                print(f"{tick - started:5.1f}s  {dist:5.2f} m to go  vx {vx:4.2f}  vyaw {vyaw:+5.2f}  "
                      f"{len(obstacles.cells):3d} cells  {note}")
            time.sleep(max(0.0, 1.0 / RATE_HZ - (time.monotonic() - tick)))
    finally:
        for _ in range(5):
            move(0.0, 0.0)
            time.sleep(0.05)
        if log:
            log.write(json.dumps({"cells": [[cx * CELL, cy * CELL] for cx, cy in obstacles.cells]}) + "\n")
            log.close()

    time.sleep(1.0)  # let it settle into the standing policy before reading where it ended up
    state = robot.latest["robot.state"]
    x, y, _ = state["odom"]["position"]
    yaw = state["odom"]["yaw"]
    # The error in the frame the goal was given in, so it reads the same way.
    dx, dy = x - gx, y - gy
    ex = dx * math.cos(frame_yaw) + dy * math.sin(frame_yaw)
    ey = -dx * math.sin(frame_yaw) + dy * math.cos(frame_yaw)
    print(f"arrived in {time.monotonic() - started:.1f} s: {math.hypot(dx, dy) * 100:.1f} cm from the goal "
          f"(x {ex * 100:+.1f} cm, y {ey * 100:+.1f} cm)"
          + (f", heading off by {math.degrees(wrap(goal_yaw - yaw)):+.1f} deg" if goal_yaw is not None else "")
          + " — by odometry")


if __name__ == "__main__":
    main()
