#!/usr/bin/env python3
"""Make BIPED-C3 dance — a simulator demo, on the stage.

    DUCK_SIM_SCENE=stage scripts/duck-sim       # terminal 1: the stage, with the dance policy
    scripts/biped60-dance.py                    # terminal 2: the whole dance, about 50 s
    scripts/biped60-dance.py --bpm 90 --loop    # slower, over and over (Ctrl-C ends it)
    scripts/biped60-dance.py --move sway        # one move, repeated; --list names them

The dancing is the dance policy (`policies-biped60/alpha_dance.onnx`, trained in the RL repo as
`Mjlab-Dance-Biped60`), which duck-sim runs as the walking policy on the stage. It follows ten live
numbers, and this script plays a choreography by streaming them through `robotd` on a beat:
`robot.move` (step forward, sideways, turn), `robot.head` (four head angles) and `robot.pose` (the
trunk's height, roll and pitch). The walking policy was trained to hold the last three at zero, so
with it the same script only walks and nods.

**A move either steps or poses.** `robotd` zeroes the twist whenever a body pose is active
(`control.rs`: body-pose mode is a standing mode, the duck's pad B), so a move that steps or turns
sends `robot.pose` inactive and keeps only its head; the others hold the pose and stand. `commands`
is that rule, and `biped60_tricks_eval.py` in the RL repo plays the dance through it too.

Every move is a function of the beat: `b` counts beats from the start of the move, so a move is
the same dance at any tempo. Amplitudes stay inside what the policy was trained on (height
-8..+1 cm, roll ±0.22, pitch -0.15..+0.30 rad, head as `HEAD_CAPS`). Standard library only.
"""

import argparse
import importlib.util
import math
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser(os.environ.get("DUCK_SIM_STATE", "~/.cache/duck-sim"))
_spec = importlib.util.spec_from_file_location("duck_nav", os.path.join(REPO, "scripts", "duck-nav.py"))
duck_nav = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(duck_nav)
Link = duck_nav.Link

RATE_HZ = 25        # `robotd` drops a move 500 ms after the last one; this is smooth enough to bounce
Z_RANGE = (-0.08, 0.01)
ROLL_MAX = 0.22
PITCH_RANGE = (-0.15, 0.30)
HEAD_CAPS = (0.35, 0.35, 1.0, 0.2)   # neck_pitch, head_pitch, head_yaw, head_roll


def down_on_beat(b):
    """0 between beats, 1 on each beat — a knee bounce lands on the beat."""
    return (1 + math.cos(2 * math.pi * b)) / 2


def side(b):
    """-1 .. +1, one side per beat."""
    return math.sin(math.pi * b)


def nod(amount):
    """Head down by `amount` (0..1), split over the neck and the head as `biped60-fetch.py` looks."""
    return {"neck_pitch": -0.3 * amount, "head_pitch": 0.3 * amount}


# Each move: (name, beats, what it is, f(b) -> dict of any of vx, vy, vyaw, z, roll, pitch,
# neck_pitch, head_pitch, head_yaw, head_roll). Missing keys are zero.
MOVES = [
    ("hello", 8, "a nod on every beat, then a look round",
     lambda b: {"z": -0.015 * down_on_beat(b), **nod(0.8 * down_on_beat(b) if b < 4 else 0),
                "head_yaw": 0 if b < 4 else 0.7 * side((b - 4) / 2)}),
    ("bounce", 8, "knees bounce on the beat, head bobs with them",
     lambda b: {"z": -0.02 - 0.05 * down_on_beat(b), **nod(0.5 * down_on_beat(b))}),
    ("sway", 8, "hips sway side to side, the head tilting against them",
     lambda b: {"z": -0.03, "roll": 0.18 * side(b), "head_roll": -0.15 * side(b),
                "head_yaw": 0.3 * side(b / 2)}),
    ("side-step", 8, "two steps left, two steps right, swaying into them",
     lambda b: {"vy": 0.22 if (b % 4) < 2 else -0.22, "roll": -0.1 * (1 if (b % 4) < 2 else -1),
                "z": -0.02 - 0.03 * down_on_beat(b), "head_yaw": 0.4 * (1 if (b % 4) < 2 else -1)}),
    ("spin", 8, "a turn to the left on the spot, looking where it goes",
     lambda b: {"vyaw": 1.1, "head_yaw": 0.45, "z": -0.02 - 0.02 * down_on_beat(b)}),
    ("bow", 8, "bow, come up, bow again",
     lambda b: {"pitch": 0.28 * math.sin(math.pi * min(b % 4, 2) / 2) ** 2,
                "z": -0.05 * math.sin(math.pi * min(b % 4, 2) / 2) ** 2,
                **nod(math.sin(math.pi * min(b % 4, 2) / 2) ** 2)}),
    ("low-groove", 8, "down low, swaying and looking left and right",
     lambda b: {"z": -0.07, "roll": 0.15 * side(b), "head_yaw": 0.6 * side(b / 2),
                "head_roll": 0.12 * side(b), "pitch": 0.08}),
    ("march", 8, "four beats forward, four back, head bobbing",
     lambda b: {"vx": 0.18 if b < 4 else -0.15, "z": -0.02 - 0.02 * down_on_beat(b),
                **nod(0.6 * down_on_beat(b))}),
    ("lean", 8, "lean back and forward with the knees, as if to the bass",
     lambda b: {"pitch": 0.12 * math.sin(math.pi * b / 2) + 0.06, "z": -0.04 - 0.03 * down_on_beat(b),
                "neck_pitch": 0.25 * math.sin(math.pi * b / 2)}),
    ("spin-back", 8, "the turn the other way",
     lambda b: {"vyaw": -1.1, "head_yaw": -0.45, "z": -0.02 - 0.02 * down_on_beat(b)}),
    ("finale", 8, "sway twice, then a deep bow, held",
     lambda b: ({"roll": 0.2 * side(b), "z": -0.03, "head_roll": -0.15 * side(b)} if b < 4 else
                {"pitch": 0.3 * min(1, (b - 4) / 1.5), "z": -0.06 * min(1, (b - 4) / 1.5),
                 **nod(min(1, (b - 4) / 1.5))})),
]


def clip(x, lo, hi):
    return max(lo, min(hi, x))


HEAD_KEYS = ("neck_pitch", "head_pitch", "head_yaw", "head_roll")


def commands(pose):
    """What one instant of a move sends: (twist, head, body or None). Body is None — the pose
    released — when the move steps or turns, since robotd would drop the step otherwise."""
    g = lambda k: float(pose.get(k, 0.0))
    twist = (g("vx"), g("vy"), g("vyaw"))
    head = tuple(clip(g(k), -cap, cap) for k, cap in zip(HEAD_KEYS, HEAD_CAPS))
    if any(abs(v) > 1e-6 for v in twist):
        return twist, head, None
    return twist, head, (clip(g("z"), *Z_RANGE), clip(g("roll"), -ROLL_MAX, ROLL_MAX), clip(g("pitch"), *PITCH_RANGE))


class Dancer:
    def __init__(self, robot):
        self.robot = robot

    def send(self, pose):
        twist, head, body = commands(pose)
        self.robot.send("robot.move", dict(zip(("vx", "vy", "vyaw"), twist)))
        self.robot.send("robot.head", dict(zip(HEAD_KEYS, head)))
        if body is None:
            self.robot.send("robot.pose", {"z": 0.0, "roll": 0.0, "pitch": 0.0, "active": False})
        else:
            self.robot.send("robot.pose", dict(zip(("z", "roll", "pitch"), body), active=True))

    def rest(self, seconds):
        """Stand still and level, the pose released, for `seconds`."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.robot.send("robot.move", {"vx": 0.0, "vy": 0.0, "vyaw": 0.0})
            self.robot.send("robot.head", {"neck_pitch": 0.0, "head_pitch": 0.0, "head_yaw": 0.0, "head_roll": 0.0})
            self.robot.send("robot.pose", {"z": 0.0, "roll": 0.0, "pitch": 0.0, "active": False})
            time.sleep(1 / RATE_HZ)

    def play(self, move, beat_s):
        name, beats, what, f = move
        print(f"  {name:<11} {what}", flush=True)
        start = time.monotonic()
        while True:
            b = (time.monotonic() - start) / beat_s
            if b >= beats:
                return
            self.send(f(b))
            time.sleep(1 / RATE_HZ)


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--bpm", type=float, default=110, help="tempo, beats a minute (default 110)")
    ap.add_argument("--move", choices=[m[0] for m in MOVES], help="dance one move, repeated")
    ap.add_argument("--loop", action="store_true", help="dance until Ctrl-C")
    ap.add_argument("--list", action="store_true", help="list the moves and stop")
    args = ap.parse_args()
    if args.list:
        for name, beats, what, _ in MOVES:
            print(f"{name:<11} {beats} beats  {what}")
        return
    sock = os.path.join(STATE, "duck.sock")
    if not os.path.exists(sock):
        raise SystemExit(f"no robotd at {sock}. Start the simulation first:\n  DUCK_SIM_SCENE=stage scripts/duck-sim")
    dancer = Dancer(Link(sock))
    beat_s = 60.0 / args.bpm
    routine = [m for m in MOVES if m[0] == args.move] if args.move else MOVES
    print(f"dancing at {args.bpm:g} bpm ({len(routine)} move{'s' * (len(routine) > 1)}"
          f"{', looped' if args.loop or args.move else ''}) — Ctrl-C to stop", flush=True)
    try:
        dancer.rest(1.0)
        while True:
            for move in routine:
                dancer.play(move, beat_s)
            if not (args.loop or args.move):
                break
    except KeyboardInterrupt:
        print()
    finally:
        dancer.rest(1.5)
        print("done — standing")


if __name__ == "__main__":
    sys.exit(main())
