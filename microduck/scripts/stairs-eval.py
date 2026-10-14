#!/usr/bin/env python3
"""Score a walking policy on the duck-sim steps and obstacle courses, against the simulator's ground truth.

    scripts/stairs-eval.py ~/Pollen/microduck_rl/exports/stairs_v6.onnx
    scripts/stairs-eval.py stairs_v4.onnx stairs_v6.onnx --runs 5
    scripts/stairs-eval.py stairs_v6.onnx --courses up,down,obstacles

For each policy, each course and each run: a fresh headless duck-sim with the policy as the walking
network, `duck-nav.py` to the course's red disc, and the trunk's true position read from the body
server the whole time. A run counts as reached when the duck ends upright within 20 cm of the disc —
by the simulator, not by odometry, which on steps is off by 10-15 cm. Every course gets the same
`duck-nav.py` command — `--step-over 0.08` walks over 1-6 cm of steps and still steers round a 20 cm
box — because one policy driven one way on every map is the point. The courses:

    up    scene_steps       six 1 cm risers up, a landing, six down; disc 3 m out
    down  scene_steps_down  six 1 cm risers down from a 6 cm platform; disc 2 m out
    hard  scene_steps_hard  1, 2 and 3 cm risers up, a landing, down; disc 2 m out
    obstacles  scene_obstacles  flat floor, a 20 cm box dead ahead and two beside the line; disc 2 m out

`policies/alpha_walking.onnx` is pointed at each policy in turn and put back as it was at the end.
"""

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALK = os.path.join(REPO, "policies", "alpha_walking.onnx")
PORT = int(os.environ.get("DUCK_SIM_PORT", "7801"))
COURSES = {
    # name: (scene, goal x, keyframe)
    "up": ("steps", 3.0, "SIT"),
    "down": ("steps_down", 2.0, "SIT_HIGH"),
    "hard": ("steps_hard", 2.0, "SIT"),
    "obstacles": ("obstacles", 2.0, "SIT"),
}
REACHED = 0.20


def watch(stop, samples):
    """Poll the body server for the trunk's true position until `stop` is set."""
    s = socket.create_connection(("127.0.0.1", PORT))
    f = s.makefile("rw")
    f.write(json.dumps({"op": "hello", "protocol": 1, "joints": 15}) + "\n")
    f.flush()
    f.readline()
    while not stop.is_set():
        f.write('{"op":"read"}\n')
        f.flush()
        r = json.loads(f.readline())
        samples.append((r["trunk"], r["imu"]["gravity"][2]))
        time.sleep(0.05)
    s.close()


def run(course, speed, timeout):
    scene, goal, keyframe = COURSES[course]
    env = dict(os.environ, DUCK_SIM_VIEWER="0", DUCK_SIM_SCENE=scene, DUCK_SIM_KEYFRAME=keyframe)
    sim = os.path.join(REPO, "scripts", "duck-sim")
    subprocess.run([sim, "down"], env=env, capture_output=True)
    if subprocess.run([sim], env=env, capture_output=True).returncode != 0:
        return None
    stop, samples = threading.Event(), []
    watcher = threading.Thread(target=watch, args=(stop, samples), daemon=True)
    watcher.start()
    started = time.monotonic()
    nav = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "duck-nav.py"), "--absolute", str(goal), "0",
         "--step-over", "0.08", "--speed", str(speed), "--timeout", str(timeout)],
        capture_output=True, text=True)
    elapsed = time.monotonic() - started
    time.sleep(1.0)
    stop.set()
    watcher.join()
    (x, y, _), gz = samples[-1]
    return {
        "reached": math.hypot(x - goal, y) < REACHED and gz < -0.9,
        "fell": any(g > -0.8 for _, g in samples),
        "error_cm": math.hypot(x - goal, y) * 100,
        "max_y": max(abs(p[1]) for p, _ in samples),
        "seconds": elapsed,
        # How duck-nav ended: its last word, which is on stderr when it gave up.
        "nav": ((nav.stderr if nav.returncode else nav.stdout).strip().splitlines() or [""])[-1],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("policies", nargs="+", help="walking policies (.onnx) to score")
    ap.add_argument("--runs", type=int, default=3, help="runs per course (default %(default)s)")
    ap.add_argument("--courses", default="up,down,hard,obstacles", help="comma-separated, of: " + ", ".join(COURSES))
    ap.add_argument("--speed", type=float, default=0.35, help="duck-nav --speed (default %(default)s)")
    ap.add_argument("--timeout", type=float, default=60.0, help="duck-nav --timeout (default %(default)s)")
    args = ap.parse_args()
    courses = args.courses.split(",")
    for c in courses:
        if c not in COURSES:
            raise SystemExit(f"no course {c!r}: " + ", ".join(COURSES))

    before = os.readlink(WALK) if os.path.islink(WALK) else None
    table = []
    try:
        for policy in args.policies:
            path = os.path.abspath(os.path.expanduser(policy))
            if not os.path.isfile(path):
                raise SystemExit(f"no such policy: {path}")
            if os.path.lexists(WALK):
                os.remove(WALK)
            os.symlink(path, WALK)
            name = os.path.basename(path)
            for course in courses:
                results = []
                for i in range(args.runs):
                    r = run(course, args.speed, args.timeout)
                    if r is None:
                        print(f"{name:20s} {course:9s} run {i + 1}: the duck did not stand up", flush=True)
                        continue
                    results.append(r)
                    print(f"{name:20s} {course:9s} run {i + 1}: {'REACHED' if r['reached'] else 'missed '} "
                          f"fell={str(r['fell']):5s} {r['error_cm']:5.0f} cm off, max |y| {r['max_y']:.2f} m, "
                          f"{r['seconds']:4.0f} s  | {r['nav']}", flush=True)
                ok = [r for r in results if r["reached"]]
                table.append((name, course, len(ok), len(results), sum(r["fell"] for r in results),
                              sum(r["seconds"] for r in ok) / len(ok) if ok else None))
    finally:
        subprocess.run([os.path.join(REPO, "scripts", "duck-sim"), "down"], capture_output=True)
        if before is not None:
            if os.path.lexists(WALK):
                os.remove(WALK)
            os.symlink(before, WALK)

    print()
    print(f"{'policy':20s} {'course':9s} {'reached':>8s} {'falls':>6s} {'mean time':>10s}")
    for name, course, ok, n, falls, secs in table:
        print(f"{name:20s} {course:9s} {ok:>4d}/{n:<3d} {falls:>6d} {f'{secs:.0f} s' if secs else '-':>10s}")


if __name__ == "__main__":
    main()
