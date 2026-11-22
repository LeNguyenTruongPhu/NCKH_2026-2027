#!/usr/bin/env python3
"""BIPED-C3 tidies the apartment: finds the things lying about, brings each to the red disc in the
office, puts it down there, and stops on the disc — a simulator demo.

    DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=course scripts/duck-sim              # terminal 1: the full course
    scripts/biped60-fetch.py                                               # terminal 2: a new random round

    DUCK_SIM_CAMERAS=a DUCK_SIM_SCENE=apartment_fetch scripts/duck-sim     # the apartment alone
    scripts/biped60-fetch.py --count 3                                     # three things this time
    scripts/biped60-fetch.py --seed 42                                     # the round seed 42 lays out, again
    scripts/biped60-fetch.py --keep --only blue_cube,green_cube            # as they lie now, some of them

**Every round is different.** The scene has five 8 cm cubes, one colour each (`make_course.PROPS`);
a round puts out `--count` of them (all five by default) and scatters them over the apartment's floor — each well clear of walls
and furniture, of the disc, of the others and of where the robot starts, and somewhere it can walk
to — and puts the rest away (the simulator's `place`/`stow`). It prints its seed; `--seed` lays the
same round out again, `--keep` fetches things where they already are.

On the full course (the RL repo's `scripts/make_course.py`) it first walks the obstacle course and
the stairs to the apartment's front door, as `biped60-goal.py` does, and starts fetching from
there; in `apartment_fetch` (`scripts/make_fetch.py`) it starts in the corridor. Which world is the
one duck-sim is running, or `--world`.

For each thing, nearest first: plan a path round the walls, the furniture, the open stairwell and
everything else on the floor, walk it — looking down at the thing over the last stretch — to stand
just short of it facing it, take it, walk to the disc, put it on a ring round the disc's centre, and
step back. When all are in, walk in between two of them to the middle of the disc and stop. The
walking is the real walking policy driven through `robotd` (`robot.move`, `robot.head`).

**Quick at each thing.** The first version stopped, turned on the spot, stopped, shuffled to within
5 cm, stopped, looked down for 1.2 s, took it and waited again — about 4.5 s standing at every
thing and every drop, besides the shuffling. Now the head goes down while it walks in, the last
stretch is straight at the thing so it arrives facing it, and it takes the thing as soon as it is
in reach (`PICK_AHEAD`/`PICK_ASIDE`, inside the simulator's grab radius with a margin) — shuffling,
with a sideways step as well as a turn, only when it is not. The disc still gets the exact shuffle:
there the spot matters.

**What is not real, and why it is only a demo.** BIPED-C3 has no hands. The simulator's `grab`
takes the thing nearest the robot's `carry` site, in front of its chest, and holds it there until
`release` sets it down in front of the robot (`mjlab_microduck/sim/props.py`). And this script
knows where everything is: the objects, the walls and the robot's own pose come straight from the
simulator rather than a camera, a map and odometry. The scene and the disc are the RL repo's
`scripts/make_fetch.py`. Standard library only, like `duck-nav.py`.
"""

import argparse
import heapq
import importlib.util
import json
import math
import os
import random
import socket
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser(os.environ.get("DUCK_SIM_STATE", "~/.cache/duck-sim"))
RL = os.path.expanduser(os.environ.get("DUCK_SIM_RL", "~/Pollen/microduck_rl"))


def has_skill(name):
    """Whether duck-sim configured robotd with this one-shot skill (its params file names it)."""
    try:
        with open(os.path.join(STATE, "robotd-duck-a.toml")) as f:
            return f'name = "{name}"' in f.read()
    except OSError:
        return False


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


duck_nav = _load("duck_nav", os.path.join(REPO, "scripts", "duck-nav.py"))
Link, wrap = duck_nav.Link, duck_nav.wrap


def running_world():
    """The world duck-sim has up, as it wrote it to its state directory, else DUCK_SIM_SCENE."""
    world = os.environ.get("DUCK_SIM_SCENE")
    try:
        with open(os.path.join(STATE, "scene")) as f:
            world = f.read().strip() or world
    except OSError:
        pass
    return "course" if world == "course" else "apartment_fetch"

RATE_HZ = 10           # `robotd` drops an intent 500 ms after the last one
CELL = 0.05            # planning grid, metres
CLEARANCE = 0.30       # paths keep this far from walls and furniture: half the shoulders and 17 cm
PROP_CLEARANCE = 0.28  # ...and this far from the centre of anything on the floor: no kicking it
STAND_OFF = 0.32       # the thing ends this far ahead of the trunk: 15 cm past the carry site, 18 cm past the
                       # toes. At 0.26 the last step's swing foot could reach a cube and knock it away.
APPROACH_RUN = 0.5     # the last stretch is straight at it, so the robot arrives facing it
GRAB_RADIUS = 0.22     # how close the carry site must be to it, across the floor
DROP_REACH = 0.26      # stand this far short of where a thing is to be set down (it lands ~24 cm ahead)
LOOK_DOWN = {"neck_pitch": -0.3, "head_pitch": 0.3, "head_yaw": 0.0, "head_roll": 0.0}  # 34° down
LOOK_AHEAD = {"neck_pitch": 0.0, "head_pitch": 0.0, "head_yaw": 0.0, "head_roll": 0.0}
LOOK_FROM = 0.8        # it looks down at the thing from this far out, walking in
PICK_AHEAD = (0.25, 0.36)  # where the thing may be ahead of the trunk to take it: the carry site is 17 cm
PICK_ASIDE = 0.07          # out and the grab reaches 22 cm, so this is within ~20 cm; 25 cm keeps the toes off it
SETTLE_S = 0.3         # standing still before taking or letting go, so the trunk is not swinging
LOOKAHEAD = 0.35
MAX_VYAW = 1.0          # the policy turns on the spot at 0.96 rad/s asked 1.0
TURN_VX = 0.10         # the policy turns best walking: a turn on the spot is a slow one
MIN_VX = 0.10
STAIRS_SPEED = 0.6     # on the course's stairs: faster climbs cleaner (see biped60-goal.py)
CLIMB_SPEED = 0.5      # ...unless the stairs specialist (climb) takes them
KICKED = 0.03          # a thing nobody is carrying that moved this far was knocked
BACK_VX = -0.15
STUCK_S = 8.0
LEG_TIMEOUT = 120.0
FACE_TOLERANCE = math.radians(12)
ALIGN_TOLERANCE = 0.05  # how near `align` gets the thing to straight ahead at its reach
ALIGN_VX = 0.12
ALIGN_VY = 0.12        # and a sideways step for what is off to one side, instead of a turn and back
MAX_COUNT = 5          # the scene has five cubes (the disc's ring would hold six)
WALL_CLEAR = 0.65      # a scattered thing lies this far from walls and furniture (and out of 1.2 m doorways)...
SPREAD = 1.0           # ...this far from the next one,
DISC_CLEAR = 0.7       # ...this far past the disc's edge,
START_CLEAR = 1.2      # ...and this far from where the robot starts fetching
STAIRWELL = (-0.8, -2.8, 0.0, -1.4)  # the corridor's open stairwell, apartment coordinates
# The apartment's rooms (apartment coordinates, xmin ymin xmax ymax). A round picks a room first and
# a spot in it second, two things a room at most: by floor area alone a third of everything landed
# in the living room and almost nothing in the furnished bedroom and office.
ROOMS = {"kitchen": (-8, 1, -2, 6), "living room": (-8, -6, -2, 1), "corridor": (-2, -6, 1, 6),
         "office": (1, -2, 8, 2), "bedroom": (1, 2, 8, 6), "bathroom": (1, -6, 8, -2)}
PER_ROOM = 2


class Sim:
    """The body server's JSON link: where things really are, and the carry trick."""

    def __init__(self, port):
        try:
            self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        except OSError:
            raise SystemExit(f"no simulator on port {port}. Start it first:\n"
                             "  DUCK_SIM_SCENE=apartment_fetch scripts/duck-sim")
        self.stream = self.sock.makefile("rw")
        self.op("hello", protocol=1, joints=15)

    def op(self, op, /, **params):
        self.stream.write(json.dumps({"op": op, **params}) + "\n")
        self.stream.flush()
        answer = json.loads(self.stream.readline())
        if "error" in answer and op not in ("grab", "release"):
            raise SystemExit(f"simulator: {op}: {answer['error']}")
        return answer

    def pose(self):
        r = self.op("read")
        w, x, y, z = r["imu"]["quat"]
        return r["trunk"][0], r["trunk"][1], math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)), r["imu"]["gravity"][2]

    def props(self):
        return {p["name"]: p for p in self.op("props")["props"]}


def path_length(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def point_at(path, s):
    for a, b in zip(path, path[1:]):
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if s <= step and step > 0:
            return a[0] + (b[0] - a[0]) * s / step, a[1] + (b[1] - a[1]) * s / step
        s -= step
    return path[-1]


def along(path, x, y, since, window=1.0):
    """How far along `path` the point nearest (x, y) is, looking only a little ahead of `since`, so a
    path that doubles back near itself cannot send progress backwards or leap ahead."""
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


class Grid:
    """Walls and furniture (grown by CLEARANCE), and the edges of the floor, as an occupancy grid
    for A*. The floor matters as much as the walls: the corridor has an open stairwell in it."""

    def __init__(self, boxes, floors):
        extent = boxes + (floors or [])
        xs = [b[0] for b in extent] + [b[2] for b in extent]
        ys = [b[1] for b in extent] + [b[3] for b in extent]
        self.x0, self.y0 = min(xs) - 0.5, min(ys) - 0.5
        self.nx = int((max(xs) + 0.5 - self.x0) / CELL) + 1
        self.ny = int((max(ys) + 0.5 - self.y0) / CELL) + 1
        self.blocked = bytearray(self.nx * self.ny)
        r = int(math.ceil(CLEARANCE / CELL))
        disc = [(a, b) for a in range(-r, r + 1) for b in range(-r, r + 1) if a * a + b * b <= r * r]
        if floors is not None:
            covered = bytearray(self.nx * self.ny)
            for x0, y0, x1, y1 in floors:
                i0, j0 = self.cell(x0, y0)
                i1, j1 = self.cell(x1, y1)
                for i in range(max(0, i0), min(self.nx, i1 + 1)):
                    for j in range(max(0, j0), min(self.ny, j1 + 1)):
                        covered[j * self.nx + i] = 1
            for j in range(self.ny):
                for i in range(self.nx):
                    if not covered[j * self.nx + i]:
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
        """A copy with a disc of `radius` blocked round each point."""
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
        """Waypoints from `start` to `goal`, corners only, or None."""
        found = self.plan_any(start, [goal])
        return found[0] if found else None

    def plan_any(self, start, goals):
        """The shortest path from `start` to whichever of `goals` is nearest by walking, corners
        only, as (waypoints, index of the goal), or None. One search for them all: one search per
        goal cost seconds on the full course, where every goal that cannot be reached is a search
        through the whole map before it gives up."""
        s = self.nearest_free(*self.cell(*start))
        targets = {}
        for k, goal in enumerate(goals):
            c = self.cell(*goal)
            if self.free(*c):
                targets.setdefault(c, k)
        if s is None or not targets:
            return None
        ends = list(targets)

        def h(c):
            return min(math.hypot(e[0] - c[0], e[1] - c[1]) for e in ends)

        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        cost, came, frontier, reached = {s: 0.0}, {}, [(0.0, s)], None
        while frontier:
            _, c = heapq.heappop(frontier)
            if c in targets:
                reached = c
                break
            for di, dj, w in moves:
                n = (c[0] + di, c[1] + dj)
                if not self.free(*n):
                    continue
                new = cost[c] + w
                if new < cost.get(n, 1e18):
                    cost[n], came[n] = new, c
                    heapq.heappush(frontier, (new + h(n), n))
        if reached is None:
            return None
        goal = goals[targets[reached]]
        cells = [reached]
        while cells[-1] != s:
            cells.append(came[cells[-1]])
        cells.reverse()
        points = [start] + [self.point(*c) for c in cells[1:-1]] + [goal]
        kept, k = [points[0]], 0
        while k < len(points) - 1:
            far = len(points) - 1
            while far > k + 1 and not self.line_free(points[k], points[far]):
                far -= 1
            kept.append(points[far])
            k = far
        return kept, targets[reached]


class Fetch:
    def __init__(self, args):
        self.args = args
        self.sim = Sim(args.port)
        sock = os.path.join(STATE, "duck.sock")
        if not os.path.exists(sock):
            raise SystemExit(f"no robotd at {sock}. Start the simulation first.")
        self.robot = Link(sock)
        room = self.sim.op("map")
        self.grid = Grid(room["obstacles"], room.get("floors"))
        self.world = args.world
        if self.world == "course":
            self.scene = _load("make_course", os.path.join(RL, "scripts", "make_course.py"))
            self.disc = self.scene.GOAL
        else:
            self.scene = _load("make_fetch", os.path.join(RL, "scripts", "make_fetch.py"))
            self.disc = self.scene.DISC
        self.slots = []  # the ring on the disc, one per thing: set in `run`
        self.used = set()
        self.kicks = 0

    # ── moving ───────────────────────────────────────────────────────────

    def move(self, vx, vyaw):
        self.robot.send("robot.move", {"vx": vx, "vy": 0.0, "vyaw": vyaw})

    def head(self, look):
        self.robot.send("robot.head", look)

    def stop(self, seconds=0.8, look=None):
        for _ in range(int(seconds * RATE_HZ)):
            self.move(0.0, 0.0)
            if look is not None:
                self.head(look)
            time.sleep(1.0 / RATE_HZ)

    def standing(self):
        return self.sim.pose()[3] < -0.7

    def walk(self, path, grid, face=None, tolerance=0.06, look_at=None):
        """Follow `path` on the robot's true pose, aiming LOOKAHEAD along it; end within `tolerance`
        of its end, then turn to `face` if it is not already facing it. With `look_at`, the head goes
        down at it once the end is LOOK_FROM away. No progress for STUCK_S and it plans again."""
        started, replans = time.monotonic(), 0
        progress, best, best_at = 0.0, 0.0, time.monotonic()
        goal = path[-1]
        while True:
            now = time.monotonic()
            if now - started > LEG_TIMEOUT or not self.standing():
                self.stop()
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
                print(f"    stuck, planning again ({replans})")
                path, progress, best, best_at = fresh, 0.0, 0.0, now
                continue
            dist = math.hypot(goal[0] - x, goal[1] - y)
            if dist < tolerance:
                break
            last = total - progress < 0.30 or dist < 0.30
            gx, gy = goal if last else point_at(path, progress + LOOKAHEAD)
            err = wrap(math.atan2(gy - y, gx - x) - yaw)
            if last and dist < 0.12 and math.cos(err) < 0.2:
                break  # a step past it: near enough, and better than circling back round
            if abs(err) > math.radians(60):
                vx, vyaw = TURN_VX, math.copysign(MAX_VYAW, err)
            elif last:
                vx = max(TURN_VX, min(self.args.speed, 0.5 * dist + MIN_VX) * math.cos(err))
                vyaw = max(-MAX_VYAW, min(MAX_VYAW, 1.5 * err))
            else:
                vx = max(MIN_VX, self.args.speed * math.cos(err) ** 2)
                vyaw = max(-MAX_VYAW, min(MAX_VYAW, 1.5 * err))
            self.move(vx, vyaw)
            if look_at is not None:
                self.head(LOOK_DOWN if total - progress < LOOK_FROM or dist < LOOK_FROM else LOOK_AHEAD)
            time.sleep(1.0 / RATE_HZ)
        look = LOOK_DOWN if look_at is not None else None
        self.stop(0.2, look=look)
        if face is not None and abs(wrap(face - self.sim.pose()[2])) > FACE_TOLERANCE:
            while time.monotonic() - started < LEG_TIMEOUT and self.standing():
                err = wrap(face - self.sim.pose()[2])
                if abs(err) < FACE_TOLERANCE:
                    break
                # On the spot: a turn that also walks steps toward whatever it is facing.
                self.move(0.0, math.copysign(min(MAX_VYAW, max(0.4, 1.5 * abs(err))), err))
                if look is not None:
                    self.head(look)
                time.sleep(1.0 / RATE_HZ)
            self.stop(0.4, look=look)
        return True

    def where(self, target):
        """`target` in the trunk's frame: (ahead, aside)."""
        x, y, yaw, _ = self.sim.pose()
        dx, dy = target[0] - x, target[1] - y
        return dx * math.cos(yaw) + dy * math.sin(yaw), -dx * math.sin(yaw) + dy * math.cos(yaw)

    def align(self, target, reach, ahead_range=None, aside=ALIGN_TOLERANCE, seconds=10.0, look=None):
        """Shuffle until `target` is `reach` straight ahead of the trunk (or anywhere in
        `ahead_range`, within `aside` of the middle): the walk ends within a few centimetres of its
        spot, but its heading can leave the thing 15-30 cm off the carry point. A sideways step
        takes out what is off to the side; a turn only what a step cannot."""
        lo, hi = ahead_range or (reach - ALIGN_TOLERANCE, reach + ALIGN_TOLERANCE)
        started = time.monotonic()
        while time.monotonic() - started < seconds and self.standing():
            ahead, side = self.where(target)
            if lo <= ahead <= hi and abs(side) < aside:
                break
            bearing = math.atan2(side, max(ahead, 0.05))
            vyaw = max(-0.6, min(0.6, 2.0 * bearing)) if abs(bearing) > math.radians(10) else 0.0
            vy = math.copysign(ALIGN_VY, side) if abs(side) > aside * 0.6 else 0.0
            if abs(bearing) > math.radians(25):
                vx, vy = 0.0, 0.0  # turn to it first
            elif ahead > hi:
                vx = ALIGN_VX
            elif ahead < lo:
                vx = -ALIGN_VX
            else:
                vx = 0.0
            self.robot.send("robot.move", {"vx": vx, "vy": vy, "vyaw": vyaw})
            if look is not None:
                self.head(look)
            time.sleep(1.0 / RATE_HZ)
        self.stop(SETTLE_S, look=look)
        return self.where(target)

    def back_off(self, seconds=1.0):
        for _ in range(int(seconds * RATE_HZ)):
            self.move(BACK_VX, 0.0)
            self.head(LOOK_AHEAD)
            time.sleep(1.0 / RATE_HZ)
        self.stop(0.3, look=LOOK_AHEAD)

    def approach(self, target, stand_off, grid, facings=None):
        """The cheapest way to stand `stand_off` short of `target` facing it, ending in a straight
        APPROACH_RUN: (length, path, heading), or None."""
        x, y, _, _ = self.sim.pose()
        around_target = grid.around([tuple(target[:2])], PROP_CLEARANCE + 0.05)
        ways = []
        for a in facings if facings is not None else [2 * math.pi * k / 16 for k in range(16)]:
            spot = (target[0] - stand_off * math.cos(a), target[1] - stand_off * math.sin(a))
            run_in = (spot[0] - APPROACH_RUN * math.cos(a), spot[1] - APPROACH_RUN * math.sin(a))
            if grid.free(*grid.cell(*spot)) and grid.line_free(run_in, spot):
                ways.append((a, spot, run_in))
        # To the run-in round the thing as well — walked straight at from its far side, a cube is
        # kicked before it is reached — then the last straight stretch at it. Every run-in is the
        # same APPROACH_RUN from its spot, so the nearest run-in is the shortest way.
        found = around_target.plan_any((x, y), [run_in for _, _, run_in in ways]) if ways else None
        if found is None:
            return None
        path, k = found
        a, spot, _ = ways[k]
        path = path + [spot]
        return path_length(path), path, a

    def lying(self):
        """Where every thing nobody is carrying lies."""
        return {n: p["pos"][:2] for n, p in self.sim.props().items() if not p["held"]}

    def check_kicks(self, before, doing):
        """Report anything that moved while the robot was `doing` something, and it was not carried."""
        for name, pos in self.lying().items():
            if name in before and math.hypot(pos[0] - before[name][0], pos[1] - before[name][1]) > KICKED:
                self.kicks += 1
                moved = math.hypot(pos[0] - before[name][0], pos[1] - before[name][1])
                print(f"    !! {name} was knocked {moved * 100:.0f} cm while {doing}")

    def to_the_door(self):
        """The full course up to the apartment's front door: the obstacle course and the stairs,
        followed by pure pursuit on the true pose, faster on the stairs."""
        s = self.scene
        path = [tuple(p) for p in s.PATH[: s.PATH.index(s.ENTRY) + 1]]
        end = s.STAIRS_X + 2 * s.RISERS * s.TREAD - s.TREAD + s.LANDING
        stairs = (s.STAIRS_X - 0.8, end + 0.3)
        climb = has_skill("climb")
        print(f"the course: obstacles, stairs{' (the stairs specialist climbs them)' if climb else ''}, "
              f"to the front door at ({path[-1][0]:.1f}, {path[-1][1]:.1f})")
        started, progress = time.monotonic(), 0.0
        while time.monotonic() - started < 240 and self.standing():
            x, y, yaw, _ = self.sim.pose()
            if math.hypot(path[-1][0] - x, path[-1][1] - y) < 0.25:
                print(f"  at the door in {time.monotonic() - started:.0f} s")
                return True
            progress = along(path, x, y, progress, window=1.5)
            gx, gy = point_at(path, progress + LOOKAHEAD)
            err = wrap(math.atan2(gy - y, gx - x) - yaw)
            on_stairs = stairs[0] <= x <= stairs[1]
            if climb and on_stairs:
                self.robot.send("robot.do", {"skill": "climb"})  # every tick keeps it chained
            speed = (CLIMB_SPEED if climb else STAIRS_SPEED) if on_stairs else 0.35
            self.move(speed * max(0.25, math.cos(err)), max(-1.0, min(1.0, 2.0 * err)))
            time.sleep(1.0 / RATE_HZ)
        self.stop()
        print("  did not reach the door")
        return False

    def others(self, name=None):
        return [p["pos"][:2] for n, p in self.sim.props().items() if n != name and not p["held"]]

    def free_slot(self):
        """The ring slot nearest the robot that nothing has been put on yet."""
        x, y, _, _ = self.sim.pose()
        free = [s for i, s in enumerate(self.slots) if i not in self.used]
        slot = min(free, key=lambda s: math.hypot(s[0] - x, s[1] - y))
        self.used.add(self.slots.index(slot))
        return slot

    # ── the job ──────────────────────────────────────────────────────────

    def fetch(self, name):
        started = time.monotonic()
        thing = self.sim.props()[name]["pos"]
        print(f"  {name}: at ({thing[0]:+.2f}, {thing[1]:+.2f})")
        grid = self.grid.around(self.others(name), PROP_CLEARANCE)
        best = self.approach(thing, STAND_OFF, grid)
        if best is None:
            print("    no way to reach it. Skipped.")
            return False
        length, path, face = best
        print(f"    walking {length:.1f} m to it")
        taken = {}
        # Twice at most: a foot can nudge it on the way in, and the second try starts from where
        # it is now.
        for attempt in range(2):
            if attempt:
                thing = self.sim.props()[name]["pos"]
                best = self.approach(thing, STAND_OFF, grid)
                if best is None:
                    break
                print(f"    trying again from {best[0]:.1f} m")
            before = self.lying()
            if not self.walk(best[1], grid, face=best[2], look_at=thing):
                print("    did not get there.")
                continue
            arrived = time.monotonic()
            self.check_kicks(before, f"walking to {name}")
            ahead, aside = self.align(self.sim.props()[name]["pos"], STAND_OFF, ahead_range=PICK_AHEAD,
                                      aside=PICK_ASIDE, look=LOOK_DOWN)
            taken = self.sim.op("grab", radius=GRAB_RADIUS)
            if "held" not in taken:
                # Just out of reach — the trunk settled a little back. A precise shuffle where it
                # stands is quicker than backing off and walking in again.
                ahead, aside = self.align(self.sim.props()[name]["pos"], STAND_OFF, look=LOOK_DOWN)
                taken = self.sim.op("grab", radius=GRAB_RADIUS)
            print(f"    took {time.monotonic() - arrived:.1f} s there: it was {ahead * 100:.0f} cm ahead, "
                  f"{aside * 100:+.0f} cm to the side")
            if "held" in taken:
                break
            print(f"    missed it: {taken.get('error')}")
            self.back_off()
        if "held" not in taken:
            print("    Skipped.")
            return False
        print(f"    picked it up ({taken['distance'] * 100:.0f} cm from the carry point) {time.monotonic() - started:.0f} s in")

        sx, sy, a = self.free_slot()
        grid = self.grid.around(self.others(name), PROP_CLEARANCE)
        best = self.approach((sx, sy), DROP_REACH, grid, facings=[a + math.pi])
        before = self.lying()
        if best is None or not self.walk(best[1], grid, face=best[2], look_at=(sx, sy)):
            print("    could not reach the disc; putting it down here")
        else:
            print(f"    walked {best[0]:.1f} m to the disc")
            self.align((sx, sy), DROP_REACH, look=LOOK_DOWN)
        self.sim.op("release")
        self.back_off()
        self.check_kicks(before | {name: self.lying()[name]}, f"bringing {name}")
        left = self.sim.props()[name]["pos"]
        miss = math.hypot(left[0] - self.disc[0], left[1] - self.disc[1])
        ok = miss < self.scene.DISC_RADIUS
        print(f"    put down {miss * 100:.0f} cm from the disc's centre — {'on the disc' if ok else 'OFF the disc'}"
              f" ({time.monotonic() - started:.0f} s for this one)")
        return ok

    # ── a new round ──────────────────────────────────────────────────────

    def start_point(self):
        """Where the robot starts fetching: the front door on the course, where it stands otherwise."""
        if self.world == "course":
            return self.scene.ENTRY
        return self.sim.pose()[:2]

    def scatter(self, count, seed):
        """Lay out a round: `count` of the scene's things, picked at random, at random spots on the
        apartment's floor that the robot can walk to; the rest put away. Returns their names."""
        rng = random.Random(seed)
        props = self.sim.props()
        pool = sorted(props)
        count = max(1, min(count, len(pool), MAX_COUNT))
        chosen = rng.sample(pool, count)
        ax, ay = getattr(self.scene, "APARTMENT_AT", (0.0, 0.0))
        start = self.start_point()
        well = (STAIRWELL[0] + ax, STAIRWELL[1] + ay, STAIRWELL[2] + ax, STAIRWELL[3] + ay)
        walls = self.sim.op("map")["obstacles"]
        boxes = [b for b in walls if b[2] > ax - 8.5 and b[0] < ax + 8.5] + [well]
        reachable = self.reachable(start)

        def approachable(spots):
            """Can the robot still get to a run-in point of every spot with all of them on the floor?
            A thing in the middle of a narrow passage would cut the rooms behind it off."""
            around = self.grid.around(spots, PROP_CLEARANCE)
            reach = self.reachable(start, around)
            run_in = STAND_OFF + APPROACH_RUN
            return all(any(around.cell(x + run_in * math.cos(a), y + run_in * math.sin(a)) in reach
                           for a in (2 * math.pi * k / 16 for k in range(16))) for x, y in spots)

        spots, rooms = [], {room: 0 for room in ROOMS}
        while len(spots) < count:
            open_rooms = [room for room, n in rooms.items() if n < PER_ROOM]
            if not open_rooms:
                break
            room = rng.choice(open_rooms)
            x0, y0, x1, y1 = ROOMS[room]
            for _ in range(400):
                x, y = ax + rng.uniform(x0 + 0.2, x1 - 0.2), ay + rng.uniform(y0 + 0.2, y1 - 0.2)
                if self.fits(x, y, spots, start, boxes, reachable, approachable):
                    spots.append((x, y))
                    rooms[room] += 1
                    break
            else:
                rooms[room] = PER_ROOM  # nowhere left in it
        chosen = chosen[: len(spots)]
        for name in pool:
            if name not in chosen:
                self.sim.op("stow", name=name)
        for name, (x, y) in zip(chosen, spots):
            self.sim.op("place", name=name, x=x, y=y, yaw=rng.uniform(-math.pi, math.pi))
        time.sleep(0.3)
        return chosen

    def fits(self, x, y, spots, start, boxes, reachable, approachable):
        """Can a thing lie at (x, y) this round: on walkable floor, clear of the disc, the start,
        the others, walls and furniture, and leaving every one of them reachable."""
        def clear_of(box):
            return math.hypot(max(box[0] - x, 0.0, x - box[2]), max(box[1] - y, 0.0, y - box[3]))

        return (self.grid.cell(x, y) in reachable
                and math.hypot(x - self.disc[0], y - self.disc[1]) >= self.scene.DISC_RADIUS + DISC_CLEAR
                and math.hypot(x - start[0], y - start[1]) >= START_CLEAR
                and all(math.hypot(x - sx, y - sy) >= SPREAD for sx, sy in spots)
                and all(clear_of(b) >= WALL_CLEAR for b in boxes)
                and approachable(spots + [(x, y)]))

    def reachable(self, start, grid=None):
        """Every cell of `grid` (the room's) the robot can walk to from `start`."""
        g = grid or self.grid
        first = g.nearest_free(*g.cell(*start))
        seen, todo = {first}, [first]
        while todo:
            i, j = todo.pop()
            for n in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if n not in seen and g.free(*n):
                    seen.add(n)
                    todo.append(n)
        return seen

    def finish(self):
        """Into the middle of the disc between two of the things on it, and stop there."""
        before = self.lying()
        gaps = [s[2] + math.pi / len(self.slots) for s in self.slots]
        x, y, _, _ = self.sim.pose()
        a = min(gaps, key=lambda g: math.hypot(self.disc[0] + 0.9 * math.cos(g) - x, self.disc[1] + 0.9 * math.sin(g) - y))
        outside = (self.disc[0] + 0.9 * math.cos(a), self.disc[1] + 0.9 * math.sin(a))
        grid = self.grid.around(self.others(), PROP_CLEARANCE)
        path = grid.plan((x, y), outside)
        if path is not None:
            self.walk(path, grid, face=a + math.pi)
        # The last stretch straight in through the gap, past the things on the ring.
        self.walk([self.sim.pose()[:2], self.disc], self.grid, tolerance=0.08)
        self.stop(1.0)
        self.check_kicks(before, "walking onto the disc")
        x, y, _, _ = self.sim.pose()
        print(f"stopped on the disc, {math.hypot(x - self.disc[0], y - self.disc[1]) * 100:.0f} cm from its centre")

    def run(self):
        props = self.sim.props()
        if self.args.keep:
            wanted = set(self.args.only.split(",")) if self.args.only else None
            todo = [n for n, p in props.items() if not p["stowed"] and (wanted is None or n in wanted)
                    and math.hypot(p["pos"][0] - self.disc[0], p["pos"][1] - self.disc[1]) > self.scene.DISC_RADIUS]
        else:
            seed = self.args.seed if self.args.seed is not None else random.randrange(10000)
            todo = self.scatter(self.args.count, seed)
            print(f"a new round (seed {seed}: --seed {seed} lays it out again): " +
                  ", ".join(f"{n} ({p[0]:+.1f}, {p[1]:+.1f})" for n, p in
                            ((n, self.sim.props()[n]["pos"]) for n in todo)))
        todo = todo[:MAX_COUNT]
        self.slots = [(self.disc[0] + self.scene.SLOT_RADIUS * math.cos(a),
                       self.disc[1] + self.scene.SLOT_RADIUS * math.sin(a), a)
                      for a in (math.pi + 2 * math.pi * k / max(5, len(todo)) for k in range(max(5, len(todo))))]
        total = len(todo)
        started = time.monotonic()
        if self.world == "course" and not self.to_the_door():
            return
        print(f"{total} to bring to the disc: {', '.join(todo)}")
        done = []
        while todo:
            x, y, _, _ = self.sim.pose()
            here = {n: p["pos"] for n, p in self.sim.props().items()}
            todo.sort(key=lambda n: math.hypot(here[n][0] - x, here[n][1] - y))
            name = todo.pop(0)
            if self.fetch(name):
                done.append(name)
        print(f"brought {len(done)} of {total} in {time.monotonic() - started:.0f} s: {', '.join(done) or 'nothing'}")
        self.finish()
        print(f"all done in {time.monotonic() - started:.0f} s; things knocked on the way: {self.kicks}")


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--count", type=int, default=5, help=f"how many things a new round puts out (default %(default)s, at most {MAX_COUNT})")
    ap.add_argument("--seed", type=int, help="lay out the round this seed gives (default: a random one, printed)")
    ap.add_argument("--keep", action="store_true", help="no new round: fetch the things where they lie now")
    ap.add_argument("--only", help="with --keep: comma-separated object names (default: all of them)")
    ap.add_argument("--speed", type=float, default=0.55, help="top walking speed, m/s (default %(default)s; it walks ~85%% of what it is asked)")
    ap.add_argument("--world", choices=("course", "apartment_fetch"), default=running_world(),
                    help="which world (default: the one duck-sim is running)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("DUCK_SIM_PORT", "7801")), help="the body server's port")
    args = ap.parse_args()
    fetch = Fetch(args)
    try:
        fetch.run()
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
    finally:
        fetch.stop(0.5)


if __name__ == "__main__":
    main()
