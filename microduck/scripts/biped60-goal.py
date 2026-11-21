#!/usr/bin/env python3
"""Walk BIPED-C3 (the 60 cm biped) to the red disc — a simulator demo.

    DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=obstacles scripts/duck-sim     # terminal 1
    scripts/biped60-goal.py                                          # terminal 2

    DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=course scripts/duck-sim        # the full course
    scripts/biped60-goal.py

`obstacles`: around the first box on its left, through the gap between the other two, onto the disc
4 m out. `course` (the RL repo's `scripts/make_course.py`): the same boxes, then up a flight of
stairs and down, in at the apartment's front door, across the living room and through two more
doors to the disc in the bathroom. Which one is DUCK_SIM_SCENE's, or `--course`. The walking is the
real walking policy driven through `robotd` with `robot.move`, the way `duck-nav.py` drives the
duck; the course's stairs need the stairs policy (`policies-biped60/`).

**Why not `duck-nav.py`.** It steers by `robotd`'s contact odometry, and that is forward kinematics
of the duck's legs — compiled into the `kinematics` crate — so on a robot with legs three times as
long it measures a fraction of the distance walked and overshoots the goal. This script reads where
the robot really is from the simulator instead, and follows a fixed path through the course rather
than the ToF. Neither exists on a robot, which is why it is only a demo. Standard library only.
"""

import argparse
import importlib.util
import json
import math
import os
import socket
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser(os.environ.get("DUCK_SIM_STATE", "~/.cache/duck-sim"))
_spec = importlib.util.spec_from_file_location("duck_nav", os.path.join(REPO, "scripts", "duck-nav.py"))
duck_nav = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(duck_nav)
Link, wrap = duck_nav.Link, duck_nav.wrap

RL = os.path.expanduser(os.environ.get("DUCK_SIM_RL", "~/Pollen/microduck_rl"))


def has_skill(name):
    """Whether duck-sim configured robotd with this one-shot skill (its params file names it)."""
    try:
        with open(os.path.join(STATE, "robotd-duck-a.toml")) as f:
            return f'name = "{name}"' in f.read()
    except OSError:
        return False


def running_scene():
    """The world duck-sim has up: what it wrote to its state directory when it started, or this
    terminal's DUCK_SIM_SCENE. The two terminals are usually not the same shell, so the variable
    set on terminal 1's command line is not here — which sent the robot round the boxes and no
    further on the full course."""
    scene = os.environ.get("DUCK_SIM_SCENE")
    try:
        with open(os.path.join(STATE, "scene")) as f:
            scene = f.read().strip() or scene
    except OSError:
        pass
    return "course" if scene == "course" else "obstacles"


def course_lines():
    """The lines through both worlds, from the RL repo's script that builds the course — one source
    for the scenes and the paths through them: the obstacle course's, and the full course's."""
    path = os.path.join(RL, "scripts", "make_course.py")
    spec = importlib.util.spec_from_file_location("make_course", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lines = {"obstacles": [tuple(p) for p in module.OBSTACLES_PATH[1:]],
             "course": [tuple(p) for p in module.PATH[1:]]}
    # Where the stairs are along x: from a little before the first step to a little past the last.
    end = module.STAIRS_X + 2 * module.RISERS * module.TREAD - module.TREAD + module.LANDING
    return lines, (module.STAIRS_X - 0.8, end + 0.3)
LOOKAHEAD = 0.35   # aim this far along the path ahead of the nearest point on it
ARRIVED = 0.12     # this close to the disc's centre is on it
MAX_VYAW = 1.0     # the walking policy trains on |vyaw| <= 1.0 ...
MIN_VX = 0.10      # ... and below this it marks time rather than going anywhere
FELL_GZ = -0.7     # gravity's z in the trunk frame: -1 upright, this much tipped is a fall
RATE_HZ = 10       # `robotd` drops an intent 500 ms after the last one


class Sim:
    """The body server's JSON link, for one thing: where the robot really is."""

    def __init__(self, port):
        try:
            self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        except OSError:
            raise SystemExit(f"no simulator on port {port}. Start it first:\n"
                             "  DUCK_SIM_ROBOT=biped60 DUCK_SIM_SCENE=obstacles scripts/duck-sim")
        self.stream = self.sock.makefile("rw")
        self.op("hello", protocol=1, joints=15)

    def op(self, name, **params):
        self.stream.write(json.dumps({"op": name, **params}) + "\n")
        self.stream.flush()
        answer = json.loads(self.stream.readline())
        if "error" in answer:
            raise SystemExit(f"simulator: {name}: {answer['error']}")
        return answer

    def pose(self):
        """Trunk x, y, yaw, and gravity's z in the trunk frame."""
        r = self.op("read")
        w, x, y, z = r["imu"]["quat"]
        yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        return r["trunk"][0], r["trunk"][1], yaw, r["imu"]["gravity"][2]


def aim_point(path, x, y):
    """The point LOOKAHEAD metres along `path` past the point on it nearest (x, y)."""
    best_d, best_s, start = float("inf"), 0.0, 0.0
    for a, b in zip(path, path[1:]):
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        t = max(0.0, min(1.0, ((x - a[0]) * (b[0] - a[0]) + (y - a[1]) * (b[1] - a[1])) / step ** 2))
        d = math.hypot(a[0] + t * (b[0] - a[0]) - x, a[1] + t * (b[1] - a[1]) - y)
        if d < best_d:
            best_d, best_s = d, start + t * step
        start += step
    s = best_s + LOOKAHEAD
    for a, b in zip(path, path[1:]):
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if s <= step:
            return a[0] + (b[0] - a[0]) * s / step, a[1] + (b[1] - a[1]) * s / step
        s -= step
    return path[-1]


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("DUCK_SIM_PORT", "7801")),
                    help="the body server's port")
    ap.add_argument("--speed", type=float, default=0.35, help="walking speed, m/s (trained up to 0.6)")
    ap.add_argument("--stairs-speed", type=float, default=0.6,
                    help="walking speed on the course's stairs, m/s. Faster climbs cleaner: over 3 cm risers "
                         "the stairs policy got over 0/6 at 0.2, 5/6 at 0.35 and 6/6 at 0.6, at 0.6 in 12 s "
                         "with one step back a run where 0.35 took 34 s and five or six")
    ap.add_argument("--climb-speed", type=float, default=0.5,
                    help="walking speed on the stairs when the stairs specialist (climb) takes them, m/s")
    ap.add_argument("--course", choices=("obstacles", "course"), default=running_scene(),
                    help="which line to follow (default: the world duck-sim is running)")
    ap.add_argument("--timeout", type=float, default=None, help="give up after this many seconds")
    args = ap.parse_args()
    lines, stairs = course_lines()
    waypoints = lines[args.course]
    goal = waypoints[-1]
    timeout = args.timeout or (240.0 if args.course == "course" else 60.0)

    sim = Sim(args.port)
    sock = os.path.join(STATE, "duck.sock")
    if not os.path.exists(sock):
        raise SystemExit(f"no robotd at {sock}. Start the simulation first.")
    robot = Link(sock)

    def move(vx, vyaw):
        robot.send("robot.move", {"vx": vx, "vy": 0.0, "vyaw": vyaw})

    x, y, yaw, gz = sim.pose()
    if gz > FELL_GZ:
        raise SystemExit("the robot is not standing — restart the simulation and try again")
    path = [(x, y)] + waypoints
    # On the course's stairs the stairs specialist drives, when duck-sim has it (`climb.onnx` in
    # the policy folder): it sees the edges and puts its feet on the treads. `robot.do climb` every
    # tick keeps it chained; steering is `robot.move` as ever. Without it, the walking policy climbs.
    climb = args.course == "course" and has_skill("climb")
    if climb:
        print("stairs: the stairs specialist (climb) will take them", flush=True)
    print(f"{args.course}: from ({x:+.2f}, {y:+.2f}) to the red disc at ({goal[0]:.1f}, {goal[1]:.1f})", flush=True)

    started = time.monotonic()
    last_print = 0.0
    try:
        while True:
            t = time.monotonic() - started
            x, y, yaw, gz = sim.pose()
            left = math.hypot(goal[0] - x, goal[1] - y)
            if gz > FELL_GZ:
                move(0.0, 0.0)
                raise SystemExit(f"the robot fell at ({x:+.2f}, {y:+.2f}) after {t:.1f} s")
            if left < ARRIVED:
                break
            if t > timeout:
                move(0.0, 0.0)
                raise SystemExit(f"gave up after {t:.0f} s, {left:.2f} m from the disc")
            ax, ay = aim_point(path, x, y)
            err = wrap(math.atan2(ay - y, ax - x) - yaw)
            vyaw = max(-MAX_VYAW, min(MAX_VYAW, 2.0 * err))
            # Slow for sharp turns and into the disc, so it stops on it instead of past it.
            on_stairs = args.course == "course" and stairs[0] <= x <= stairs[1]
            if climb and on_stairs:
                robot.send("robot.do", {"skill": "climb"})
            speed = (args.climb_speed if climb else args.stairs_speed) if on_stairs else args.speed
            vx = speed * max(0.25, math.cos(err))
            vx = max(MIN_VX, min(vx, 0.6 * left + 0.05))
            move(vx, vyaw)
            if t - last_print >= (1.0 if args.course == "obstacles" else 3.0):
                last_print = t
                print(f"  {t:4.1f} s  at ({x:+.2f}, {y:+.2f})  facing {math.degrees(yaw):+4.0f}°  "
                      f"{left:.2f} m to go", flush=True)
            time.sleep(1.0 / RATE_HZ)
    except KeyboardInterrupt:
        move(0.0, 0.0)
        print("\nstopped")
        sys.exit(130)

    for _ in range(5):  # zero twist: `robotd` holds it standing
        move(0.0, 0.0)
        time.sleep(0.1)
    x, y, _, _ = sim.pose()
    print(f"on the red disc: ({x:+.2f}, {y:+.2f}), {math.hypot(goal[0] - x, goal[1] - y):.2f} m from its centre, "
          f"in {time.monotonic() - started:.1f} s")


if __name__ == "__main__":
    main()
