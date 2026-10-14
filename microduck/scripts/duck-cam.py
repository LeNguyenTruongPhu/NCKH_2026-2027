#!/usr/bin/env python3
"""See what a simulated duck's head camera sees, straight off the simulator's frame port.

    DUCK_SIM_CAMERAS=a scripts/duck-sim       # a duck with an eye
    scripts/duck-cam.py                       # a window on duck a's camera: s saves a frame, q quits
    scripts/duck-cam.py --duck b              # another duck's (DUCK_SIM_CAMERAS=a,b or all)
    scripts/duck-cam.py --snapshot view.png   # one frame to a file, no window
    scripts/duck-cam.py --rotate 0            # as the sensor reads it, a quarter turn off

This is the same stream `mediad` captures — 640x360 UYVY, each frame a four-byte little-endian
length and then the bytes — read directly, for a machine where `mediad` does not build (it needs
GStreamer 1.22) or a session that only wants to look. It needs OpenCV (`python3 -c "import cv2"`).

**Turned upright, as the console turns it.** The head camera is mounted a quarter turn off, and the
simulated one is rolled the same way on purpose, so a raw frame has the floor down one side.
`mediad --rotate` (90 clockwise by default) is where that fact lives and what every display
applies; this does the same, and `--rotate 0` shows the frame as it arrives.
"""

import argparse
import os
import socket
import struct
import sys
import time

import cv2
import numpy as np

# OpenCV points its own Qt at a font directory beside itself — set on import, so it is overridden
# here, after — finds none there, and says so for every window event. The system's fonts will do.
if os.path.isdir("/usr/share/fonts/truetype/dejavu"):
    os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts/truetype/dejavu"

WIDTH, HEIGHT = 640, 360
FRAME_PORT = int(os.environ.get("DUCK_SIM_FRAME_PORT", "7901"))
# Degrees clockwise, as `mediad --rotate` takes them.
ROTATIONS = {0: None, 90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def frames(port, rotate):
    """Every frame the camera sends, as BGR turned `rotate` degrees clockwise, until it hangs up."""
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    except OSError as e:
        raise SystemExit(f"no camera on port {port} ({e}) — start the duck with DUCK_SIM_CAMERAS=a")
    stream = sock.makefile("rb")
    while True:
        head = stream.read(4)
        if len(head) < 4:
            return
        (length,) = struct.unpack("<I", head)
        data = stream.read(length)
        if len(data) < length:
            return
        if length != WIDTH * HEIGHT * 2:
            raise SystemExit(f"a {length}-byte frame is not {WIDTH}x{HEIGHT} UYVY")
        uyvy = np.frombuffer(data, np.uint8).reshape(HEIGHT, WIDTH, 2)
        frame = cv2.cvtColor(uyvy, cv2.COLOR_YUV2BGR_UYVY)
        yield frame if ROTATIONS[rotate] is None else cv2.rotate(frame, ROTATIONS[rotate])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--duck", default="a", help="which duck: a, b, c... (default %(default)s)")
    ap.add_argument("--snapshot", metavar="PNG", help="save one frame here and exit, no window")
    ap.add_argument("--rotate", type=int, default=90, choices=sorted(ROTATIONS),
                    help="degrees clockwise to turn each frame, as mediad --rotate (default %(default)s: upright)")
    args = ap.parse_args()
    port = FRAME_PORT + ord(args.duck) - ord("a")

    if args.snapshot:
        frame = next(frames(port, args.rotate), None)
        if frame is None:
            raise SystemExit("the camera hung up before a frame arrived")
        cv2.imwrite(args.snapshot, frame)
        print(f"duck {args.duck}: {frame.shape[1]}x{frame.shape[0]} frame saved to {args.snapshot}")
        return

    title = f"duck {args.duck} camera (s: save, q: quit)"
    count, started = 0, time.monotonic()
    for frame in frames(port, args.rotate):
        count += 1
        fps = count / max(1e-3, time.monotonic() - started)
        cv2.putText(frame, f"{fps:4.1f} fps", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow(title, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            name = time.strftime("duck-cam-%H%M%S.png")
            cv2.imwrite(name, frame)
            print(f"saved {name}")
    else:
        print("the camera hung up", file=sys.stderr)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
