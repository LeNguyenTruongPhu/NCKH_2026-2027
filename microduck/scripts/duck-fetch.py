#!/usr/bin/env python3
"""Fetch the loose things lying about the apartment and bring them to the drop zone — a simulator demo.

    ln -sfn ~/.cache/duck-sim/policies/releases/seed-v1/alpha_walking.onnx policies/alpha_walking.onnx
    DUCK_SIM_SCENE=apartment_fetch scripts/duck-sim
    scripts/duck-fetch.py                         # everything, nearest first
    scripts/duck-fetch.py --only ball_2,obj_3     # some of it

    DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=apartment_fetch scripts/duck-sim     # with an eye, and then
    scripts/duck-fetch.py --camera                # a window on what the duck sees as it works
    scripts/duck-fetch.py --snapshots fetch-shots # its view at each step, saved as PNGs

For each object: plan a path through the rooms to a spot 10 cm short of it, walk there, face it,
bow with the `ground_pick` skill, take it at the bottom of the bow, walk to the red disc in the
corridor, bow again and let it go. The walking is the real walking policy driven through `robotd`,
and the bow is the real ground-pick policy.

**What is not real, and why it is only a demo.** The duck in MuJoCo has no mouth joint, so it
cannot grip anything; the simulator's `grab` hangs the object under the beak tip until `release`
(`mjlab_microduck/sim/props.py`). And this script knows where everything is: it reads the objects,
the walls and the duck's own pose straight from the simulator rather than from a camera, a map and
odometry. None of that exists on a robot. Standard library only, like `duck-nav.py`.

**The walking policy has to turn well** — the planner's paths have corners. The official `seed-v1`
walker does; the stairs policies (`stairs_v8`) do not, and stand still at the first corner.
"""

import argparse
import heapq
import importlib.util
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser(os.environ.get("DUCK_SIM_STATE", "~/.cache/duck-sim"))
CAM = os.path.join(REPO, "scripts", "duck-cam.py")
FRAME_PORT = int(os.environ.get("DUCK_SIM_FRAME_PORT", "7901"))
_spec = importlib.util.spec_from_file_location("duck_nav", os.path.join(REPO, "scripts", "duck-nav.py"))
duck_nav = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(duck_nav)
Link, wrap = duck_nav.Link, duck_nav.wrap

GOAL = (-0.25, 1.10)    # the drop zone's centre, as scene_apartment_fetch.xml has it
ZONE = 0.30             # and its radius: the 3x3 grid of drop slots below, and a few centimetres of landing
PROP_CLEARANCE = 0.14   # paths keep this far from the centre of anything else lying about: half
                        # the duck's width and half a ball, so it walks round them, not through them
DROP_GAP = 0.11         # a drop goes this far from everything already in the zone, centre to centre
BOW_REACH = 0.14        # a bow sweeps the head this far ahead of where the duck stands...
BOW_CLEARANCE = 0.09    # ...and nothing else may lie within this of that strip: half a head and a prop
# **Where things go in the drop zone, in order.** A 3x3 grid 12 cm apart, filled from the far (north)
# row to the near one and always approached from the south, facing north. Scattered round the centre,
# the seventh object found every side of the zone blocked by the first six; filled from the back,
# the way in to the next slot is always the rows that are still empty.
DROP_SLOTS = [(GOAL[0] + dx, GOAL[1] + dy) for dy in (0.12, 0.0, -0.12) for dx in (0.0, -0.12, 0.12)]
DROP_FACING = math.pi / 2
REACH = 0.11            # how far in front of the trunk the beak tip lands at the bottom of a bow
DROP_REACH = 0.18       # where a released object lands: 3 cm beyond the beak tip, clear of the head
STAND_OFF = 0.10        # where the trunk stops short of the object: the walk ends a centimetre or two
                        # short of where it was sent, so a little less than REACH
LOOKAHEAD = 0.30        # how far along the path the duck aims
STUCK_S = 8.0           # no progress along the path for this long, and it plans again
GRAB_Z = 0.045          # beak tip below this, in the bow: close enough to take hold
BOWED_Z = 0.10          # below this the bow is well under way: the beak stopping here is the bottom
CELL = 0.05             # planning grid, metres
CLEARANCE = 0.17        # walls are grown by this: the duck's half width and a margin
RATE_HZ = 10
MAX_VYAW = 0.8
LEG_TIMEOUT = 90.0
# **The walking policy will not start a turn from a standstill.** A pure yaw command to a standing
# duck — 0.8 or 1.0 rad/s — rocks it 6-9 degrees in three seconds and goes nowhere; a step forward
# of 0.2 with the same turn starts the gait and turns 75 degrees in the same time, for 18 cm of
# ground. So every turn walks a little, and backing up asks for 0.4: 0.3 backwards does nothing.
TURN_VX = 0.20
BACK_VX = -0.40
FACE_TOLERANCE = math.radians(12)   # 2 cm of beak at REACH, and a turn this small rarely starts
APPROACH_RUN = 0.30     # the last stretch to an object is a straight line this long, ending facing it


def segment_distance(p, a, b):
    """How far point `p` is from the segment `a`-`b`, in the plane."""
    (px, py), (ax, ay), (bx, by) = p[:2], a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def path_length(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def point_at(path, s):
    """The point `s` metres along `path` (its end, past the end)."""
    for a, b in zip(path, path[1:]):
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if s <= step and step > 0:
            return a[0] + (b[0] - a[0]) * s / step, a[1] + (b[1] - a[1]) * s / step
        s -= step
    return path[-1]


def along(path, x, y, since, window=1.0):
    """How far along `path` the point nearest (x, y) is — looking from `since` to `since + window`
    only, so a path that doubles back near itself cannot send progress backwards or leap ahead."""
    best, best_d, start = since, float("inf"), 0.0
    for a, b in zip(path, path[1:]):
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if step > 0 and start + step >= since - 0.05 and start <= since + window:
            t = max(0.0, min(1.0, ((x - a[0]) * (b[0] - a[0]) + (y - a[1]) * (b[1] - a[1])) / step ** 2))
            d = math.hypot(a[0] + t * (b[0] - a[0]) - x, a[1] + t * (b[1] - a[1]) - y)
            s = start + t * step
            if d < best_d and since - 0.05 <= s <= since + window:
                best, best_d = s, d
        start += step
    return max(since, best)


class Sim:
    """The body server's JSON link: ground truth and the carrying trick."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port))
        self.stream = self.sock.makefile("rw")
        self.op("hello", protocol=1, joints=15)

    def op(self, name, **params):
        self.stream.write(json.dumps({"op": name, **params}) + "\n")
        self.stream.flush()
        answer = json.loads(self.stream.readline())
        if "error" in answer and name not in ("grab", "release"):
            raise SystemExit(f"simulator: {name}: {answer['error']}")
        return answer

    def pose(self):
        """Trunk x, y, yaw and the up-ness of gravity — where the duck really is."""
        r = self.op("read")
        w, x, y, z = r["imu"]["quat"]
        return r["trunk"][0], r["trunk"][1], math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)), r["imu"]["gravity"][2]


class Grid:
    """The walls, and the edges of the floor, as an occupancy grid grown by CLEARANCE, for A*.

    The floor matters as much as the walls: the apartment's corridor has an open stairwell in it,
    and a map of walls alone routes straight across the hole.
    """

    def __init__(self, boxes, floors=None):
        extent = boxes + (floors or [])
        xs = [b[0] for b in extent] + [b[2] for b in extent]
        ys = [b[1] for b in extent] + [b[3] for b in extent]
        self.x0, self.y0 = min(xs) - 0.5, min(ys) - 0.5
        self.nx = int((max(xs) + 0.5 - self.x0) / CELL) + 1
        self.ny = int((max(ys) + 0.5 - self.y0) / CELL) + 1
        self.blocked = bytearray(self.nx * self.ny)
        if floors is not None:
            # Every cell within CLEARANCE of a cell with no floor under it is out of bounds.
            covered = bytearray(self.nx * self.ny)
            for x0, y0, x1, y1 in floors:
                i0, j0 = self.cell(x0, y0)
                i1, j1 = self.cell(x1, y1)
                for i in range(max(0, i0), min(self.nx, i1 + 1)):
                    for j in range(max(0, j0), min(self.ny, j1 + 1)):
                        covered[j * self.nx + i] = 1
            r = int(math.ceil(CLEARANCE / CELL))
            disc = [(a, b) for a in range(-r, r + 1) for b in range(-r, r + 1) if a * a + b * b <= r * r]
            for j in range(self.ny):
                for i in range(self.nx):
                    if covered[j * self.nx + i]:
                        continue
                    for a, b in disc:
                        if 0 <= i + a < self.nx and 0 <= j + b < self.ny:
                            self.blocked[(j + b) * self.nx + i + a] = 1
        for x0, y0, x1, y1 in boxes:
            i0, j0 = self.cell(x0 - CLEARANCE, y0 - CLEARANCE)
            i1, j1 = self.cell(x1 + CLEARANCE, y1 + CLEARANCE)
            for i in range(max(0, i0), min(self.nx, i1 + 1)):
                for j in range(max(0, j0), min(self.ny, j1 + 1)):
                    self.blocked[j * self.nx + i] = 1

    def cell(self, x, y):
        return int(round((x - self.x0) / CELL)), int(round((y - self.y0) / CELL))

    def point(self, i, j):
        return self.x0 + i * CELL, self.y0 + j * CELL

    def around(self, points, radius):
        """A copy with a disc of `radius` blocked round each point — the loose things on the floor."""
        grid = Grid.__new__(Grid)
        grid.__dict__.update(self.__dict__)
        grid.blocked = bytearray(self.blocked)
        r = int(math.ceil(radius / CELL))
        for x, y in points:
            ci, cj = self.cell(x, y)
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    if a * a + b * b <= r * r and 0 <= ci + a < self.nx and 0 <= cj + b < self.ny:
                        grid.blocked[(cj + b) * self.nx + ci + a] = 1
        return grid

    def free(self, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny and not self.blocked[j * self.nx + i]

    def nearest_free(self, i, j, limit=12):
        """The closest free cell — for a duck standing nearer a wall than the clearance allows."""
        if self.free(i, j):
            return i, j
        for r in range(1, limit):
            ring = [(i + a, j + b) for a in range(-r, r + 1) for b in range(-r, r + 1) if max(abs(a), abs(b)) == r]
            ring = [c for c in ring if self.free(*c)]
            if ring:
                return min(ring, key=lambda c: (c[0] - i) ** 2 + (c[1] - j) ** 2)
        return None

    def line_free(self, a, b):
        (x0, y0), (x1, y1) = a, b
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / (CELL / 2)))
        return all(self.free(*self.cell(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)) for k in range(steps + 1))

    def plan(self, start, goal):
        """Waypoints from `start` to `goal` round the walls, or None. Corners only, not every cell."""
        s = self.nearest_free(*self.cell(*start))
        g = self.cell(*goal)
        if s is None or not self.free(*g):
            return None
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        cost, came, frontier = {s: 0.0}, {}, [(0.0, s)]
        while frontier:
            _, c = heapq.heappop(frontier)
            if c == g:
                break
            for di, dj, w in moves:
                n = (c[0] + di, c[1] + dj)
                if not self.free(*n):
                    continue
                new = cost[c] + w
                if new < cost.get(n, 1e18):
                    cost[n], came[n] = new, c
                    heapq.heappush(frontier, (new + math.hypot(g[0] - n[0], g[1] - n[1]), n))
        if g not in came and g != s:
            return None
        cells = [g]
        while cells[-1] != s:
            cells.append(came[cells[-1]])
        cells.reverse()
        points = [start] + [self.point(*c) for c in cells[1:-1]] + [goal]
        # Pull the string: keep only the points a straight line cannot skip.
        kept, k = [points[0]], 0
        while k < len(points) - 1:
            far = len(points) - 1
            while far > k + 1 and not self.line_free(points[k], points[far]):
                far -= 1
            kept.append(points[far])
            k = far
        return kept

    def length(self, path):
        return path_length(path)


class Fetch:
    def __init__(self, args):
        self.args = args
        self.sim = Sim(args.port)
        self.robot = Link(args.socket)
        self.robot.call("robot.subscribe", {"hz": 20})
        if self.robot.wait_for("robot.state") is None:
            raise SystemExit("robotd is not streaming state")
        room = self.sim.op("map")
        self.grid = Grid(room["obstacles"], room.get("floors"))
        self.min_vx = max(0.10, 0.6 * args.speed)
        self.log = open(args.log, "w") if args.log else None
        self.t0 = time.monotonic()
        self.shots, self.shot, self.shooting = args.snapshots, 0, []
        if (args.snapshots or args.camera) and not camera_up():
            print(f"no camera on port {FRAME_PORT} — start the duck with DUCK_SIM_CAMERAS=a. Carrying on without one.")
            self.shots = args.camera = None
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)

    def snapshot(self, name, stage):
        """What the duck sees right now, saved as `NN-name-stage.png` in --snapshots.

        In the background: grabbing a frame takes a few hundred milliseconds, and a walk that
        stopped sending for that long would be stopped by robotd's deadman.
        """
        if not self.shots:
            return
        self.shot += 1
        path = os.path.join(self.shots, f"{self.shot:02d}-{name}-{stage}.png")

        def shoot():
            done = subprocess.run([sys.executable, CAM, "--snapshot", path], capture_output=True, text=True, timeout=10)
            if done.returncode != 0 and self.shots:
                print(f"    no photo ({(done.stderr.strip().splitlines() or ['duck-cam failed'])[-1]}); no more tried")
                self.shots = None

        print(f"    photo: {path}")
        self.shooting.append(threading.Thread(target=shoot, daemon=True))
        self.shooting[-1].start()

    def note(self, text):
        print(f"    {text}")
        if self.log:
            self.log.write(json.dumps({"t": round(time.monotonic() - self.t0, 2), "note": text}) + "\n")

    def trace(self, x, y, yaw, progress, total, dist):
        if self.log:
            self.log.write(json.dumps({"t": round(time.monotonic() - self.t0, 2), "x": round(x, 3), "y": round(y, 3),
                                       "yaw": round(yaw, 3), "along": round(progress, 2), "of": round(total, 2),
                                       "left": round(dist, 3)}) + "\n")

    def move(self, vx, vyaw):
        self.robot.send("robot.move", {"vx": vx, "vy": 0.0, "vyaw": vyaw})

    def stop(self, settle=0.8):
        for _ in range(int(settle * RATE_HZ)):
            self.move(0.0, 0.0)
            time.sleep(1.0 / RATE_HZ)

    def upright(self):
        """Wait out a fall: robotd lies the duck down and stands it up again on its own."""
        state = self.robot.latest["robot.state"]
        if not (state["safety"]["fallen"] or state["safety"]["limp"]):
            return True
        print("    fell — waiting for it to get up")
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            self.move(0.0, 0.0)
            state = self.robot.latest["robot.state"]
            if not state["safety"]["fallen"] and not state["safety"]["limp"] and self.sim.pose()[3] < -0.95:
                time.sleep(1.5)
                return True
            time.sleep(1.0 / RATE_HZ)
        return False

    def walk(self, path, grid, face=None, tolerance=0.04, photo=None):
        """Follow `path` on the duck's true pose, end within `tolerance`, then turn to `face`.

        **Along the path, not from corner to corner.** Steering at the next waypoint until it is
        within reach orbits it for good when a corner is cut wider than the duck's turning circle
        (26 cm at the slowest walk and the fastest turn) — every failed leg of the first full run.
        So progress is the distance travelled along the path, which only grows, and the duck aims
        LOOKAHEAD further on. No progress for STUCK_S, and it plans again from where it stands.
        """
        started, replans = time.monotonic(), 0
        progress, best, best_at = 0.0, 0.0, time.monotonic()
        goal = path[-1]
        while True:
            now = time.monotonic()
            if now - started > LEG_TIMEOUT:
                self.stop()
                return False
            if not self.upright():
                return False
            x, y, yaw, _ = self.sim.pose()
            progress = along(path, x, y, progress)
            total = path_length(path)
            if progress > best + 0.05:
                best, best_at = progress, now
            elif now - best_at > STUCK_S:
                replans += 1
                fresh = grid.plan((x, y), goal)
                if fresh is None or replans > 3:
                    self.stop()
                    return False
                self.note(f"stuck, planning again ({replans})")
                path, progress, best, best_at = fresh, 0.0, 0.0, now
                continue
            dist = math.hypot(goal[0] - x, goal[1] - y)
            if dist < tolerance:
                break
            if photo is not None and total - progress < APPROACH_RUN + 0.05:
                photo()  # lined up on the straight run in: what it is walking at is in view
                photo = None
            last = total - progress < 0.30 or dist < 0.30
            gx, gy = goal if last else point_at(path, progress + LOOKAHEAD)
            err = wrap(math.atan2(gy - y, gx - x) - yaw)
            self.trace(x, y, yaw, progress, total, dist)
            if last and dist < 0.12 and math.cos(err) < 0.2:
                break  # a step past it: close enough for the beak, and better than a loop back round
            if abs(err) > math.radians(60):
                # Far off the line: a tight walking turn, since a turn on the spot never starts.
                vx, vyaw = TURN_VX, math.copysign(MAX_VYAW, err)
            elif last:
                # Close in along the line, slowing; the approach was planned to arrive facing it.
                vx = max(TURN_VX, min(self.args.speed, 0.5 * dist + self.min_vx) * math.cos(err))
                vyaw = max(-MAX_VYAW, min(MAX_VYAW, 1.5 * err))
            else:
                vx = max(self.min_vx, self.args.speed * math.cos(err) ** 2)
                vyaw = max(-MAX_VYAW, min(MAX_VYAW, 1.5 * err))
            self.move(vx, vyaw)
            time.sleep(1.0 / RATE_HZ)
        self.stop()
        if face is not None and abs(wrap(face - self.sim.pose()[2])) > FACE_TOLERANCE:
            # Rare, with the straight run in: a short walking turn, then stop wherever it is.
            while time.monotonic() - started < LEG_TIMEOUT and self.upright():
                err = wrap(face - self.sim.pose()[2])
                if abs(err) < FACE_TOLERANCE:
                    break
                self.move(TURN_VX, math.copysign(MAX_VYAW, err))
                time.sleep(1.0 / RATE_HZ)
            self.stop()
        return True

    def back_off(self, seconds=1.0):
        """Step back from what was just put down, before turning away and kicking it."""
        for _ in range(int(seconds * RATE_HZ)):
            self.move(BACK_VX, 0.0)
            time.sleep(1.0 / RATE_HZ)
        self.stop(0.5)

    def bow(self, at_bottom, rising=False):
        """The ground-pick skill; `at_bottom` runs once the beak is down, and its answer is returned.

        "Down" is the bottom of the bow, wherever that is: the floor, or the top of the thing
        being picked up, which a beak that lands on a cube never gets below — waiting for the
        floor there timed out with the duck standing up again. So taking hold happens as soon as
        the beak is near the floor or has stopped going down. Letting go waits for the way back up
        (`rising`): released while the beak was still going down, a ball was under a head still
        bowing into it, and was shoved a metre across the corridor.
        """
        self.robot.call("robot.do", {"skill": "ground_pick"})
        started, lowest, previous = time.monotonic(), 1.0, 1.0
        while time.monotonic() - started < 2.5:
            beak = self.sim.op("props")["beak"]
            if beak:
                z = beak[2]
                lowest = min(lowest, z)
                bowed = lowest < BOWED_Z
                settled = bowed and z > previous - 0.002  # down, and no lower than 50 ms ago
                if not rising and (z < GRAB_Z or settled):
                    break
                if rising and bowed and z > lowest + 0.01:
                    break
                previous = z
            time.sleep(0.05)
        answer = at_bottom()
        # Wait for the skill to hand back to the standing policy, then a moment to settle.
        while time.monotonic() - started < 6.0 and self.robot.latest["robot.state"]["policy"] == "ground_pick":
            time.sleep(0.1)
        time.sleep(0.6)
        return answer

    def approach(self, target, stand_off, grid, avoid=(), facings=None):
        """The cheapest way to stand `stand_off` short of `target`, facing it: the path, ending in a
        straight APPROACH_RUN towards it so the duck arrives already pointing the right way, and
        that heading. None when no side of it can be reached."""
        x, y, _, _ = self.sim.pose()
        best = None
        for a in facings if facings is not None else [2 * math.pi * k / 16 for k in range(16)]:
            spot = (target[0] - stand_off * math.cos(a), target[1] - stand_off * math.sin(a))
            run_in = (spot[0] - APPROACH_RUN * math.cos(a), spot[1] - APPROACH_RUN * math.sin(a))
            if not (grid.free(*grid.cell(*spot)) and grid.line_free(run_in, spot)):
                continue
            # The bow sweeps the head from where the duck stands to BOW_REACH ahead: anything in
            # that strip is struck on the way down and flicked on the way up.
            reach = (spot[0] + BOW_REACH * math.cos(a), spot[1] + BOW_REACH * math.sin(a))
            if any(segment_distance(o, spot, reach) < BOW_CLEARANCE for o in avoid):
                continue
            path = grid.plan((x, y), run_in)
            if path is None:
                continue
            path = path + [spot]
            if best is None or grid.length(path) < best[0]:
                best = (grid.length(path), path, a)
        return best

    def others(self, name):
        """Where everything but `name` lies, so paths go round it."""
        return [p["pos"][:2] for p in self.sim.op("props")["props"] if p["name"] != name and not p["held"]]

    def drop_spot(self, name):
        """The first of DROP_SLOTS that is DROP_GAP clear of what is already in the zone."""
        zone = [o for o in self.others(name) if math.hypot(o[0] - GOAL[0], o[1] - GOAL[1]) < 0.5]
        for slot in DROP_SLOTS:
            if all(math.hypot(slot[0] - o[0], slot[1] - o[1]) >= DROP_GAP for o in zone):
                return slot
        return DROP_SLOTS[-1]

    def fetch(self, name):
        taken = None
        # Twice at most: walking up to a cube can nudge it, and a bow over where it used to be
        # comes up empty. The second try starts from where it is now.
        for attempt in range(2):
            thing = {p["name"]: p for p in self.sim.op("props")["props"]}[name]["pos"]
            print(f"  {name}: at ({thing[0]:+.2f}, {thing[1]:+.2f})" + (" — trying again" if attempt else ""))
            others = self.others(name)
            grid = self.grid.around(others, PROP_CLEARANCE)
            best = self.approach(thing, STAND_OFF, grid, others) or self.approach(thing, STAND_OFF, grid)
            if best is None:
                print("    no way to reach it — inside furniture, or against a wall. Skipped.")
                return False
            length, path, face = best
            print(f"    walking {length:.1f} m, {len(path) - 1} legs")
            if not self.walk(path, grid, face=face, photo=lambda: self.snapshot(name, "approach")):
                print("    did not get there. Skipped.")
                return False
            x, y, yaw, _ = self.sim.pose()
            now = {p["name"]: p for p in self.sim.op("props")["props"]}[name]["pos"]
            ahead = (now[0] - x) * math.cos(yaw) + (now[1] - y) * math.sin(yaw)
            aside = -(now[0] - x) * math.sin(yaw) + (now[1] - y) * math.cos(yaw)
            print(f"    in place: it is {ahead * 100:.0f} cm ahead and {aside * 100:+.0f} cm to the side"
                  + (f" (it moved {math.hypot(now[0] - thing[0], now[1] - thing[1]) * 100:.0f} cm)"
                     if math.hypot(now[0] - thing[0], now[1] - thing[1]) > 0.02 else ""))
            taken = self.bow(lambda: self.sim.op("grab", radius=self.args.radius))
            if "held" in taken:
                break
            print(f"    missed it: {taken.get('error')}")
            self.back_off()
        if "held" not in taken:
            return False
        print(f"    picked up ({taken['distance'] * 100:.0f} cm from the beak)")

        spot = self.drop_spot(name)
        others = self.others(name)
        grid = self.grid.around(others, PROP_CLEARANCE)
        best = (self.approach(spot, DROP_REACH, grid, others, facings=[DROP_FACING])
                or self.approach(spot, DROP_REACH, grid, others)
                or self.approach(spot, DROP_REACH, grid))
        if best is None or not self.walk(best[1], grid, face=best[2], photo=lambda: self.snapshot(name, "zone")):
            print("    could not get back to the drop zone; putting it down here")
        self.bow(lambda: self.sim.op("release"), rising=True)
        self.back_off()
        self.snapshot(name, "put-down")
        left = {p["name"]: p for p in self.sim.op("props")["props"]}[name]["pos"]
        miss = math.hypot(left[0] - GOAL[0], left[1] - GOAL[1])
        print(f"    put down {miss * 100:.0f} cm from the centre of the drop zone")
        return miss < ZONE

    def run(self):
        props = self.sim.op("props")["props"]
        wanted = set(self.args.only.split(",")) if self.args.only else None
        todo = [p["name"] for p in props
                if (wanted is None or p["name"] in wanted)
                and math.hypot(p["pos"][0] - GOAL[0], p["pos"][1] - GOAL[1]) > ZONE]
        print(f"{len(todo)} to fetch: {', '.join(todo)}")
        done, started = [], time.monotonic()
        while todo:
            x, y, _, _ = self.sim.pose()
            here = {p["name"]: p["pos"] for p in self.sim.op("props")["props"]}
            todo.sort(key=lambda n: math.hypot(here[n][0] - x, here[n][1] - y))
            name = todo.pop(0)
            if self.fetch(name):
                done.append(name)
        print(f"brought {len(done)} back in {time.monotonic() - started:.0f} s: {', '.join(done) or 'nothing'}")
        for shooting in self.shooting:
            shooting.join(timeout=10)


def camera_up():
    """Whether duck a's camera is serving frames — the simulator only renders one when asked."""
    try:
        socket.create_connection(("127.0.0.1", FRAME_PORT), timeout=1).close()
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="comma-separated object names (default: every one)")
    ap.add_argument("--speed", type=float, default=0.35, help="top walking speed, m/s (default %(default)s)")
    ap.add_argument("--radius", type=float, default=0.15, help="how close the beak must get to take hold (default %(default)s)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DUCK_SIM_PORT", "7801")), help="the body server's port")
    ap.add_argument("--socket", default=os.path.join(STATE, "duck.sock"), help="robotd's socket")
    ap.add_argument("--log", help="write every control tick as JSON lines, for working out where a leg went wrong")
    ap.add_argument("--camera", action="store_true",
                    help="open a window on the duck's camera while it works (scripts/duck-cam.py; needs DUCK_SIM_CAMERAS=a)")
    ap.add_argument("--snapshots", metavar="DIR",
                    help="save the duck's view as it walks up to each object, walks up to the drop zone, and has put it down")
    args = ap.parse_args()
    fetch = Fetch(args)
    window = subprocess.Popen([sys.executable, CAM]) if args.camera else None
    try:
        fetch.run()
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
    finally:
        fetch.stop(0.5)
        if window is not None:
            window.terminate()


if __name__ == "__main__":
    main()
