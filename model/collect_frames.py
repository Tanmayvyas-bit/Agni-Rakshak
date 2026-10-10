"""Collect your own training images from the laptop webcam or a video (Tanishka, week 1-2).

Self-collected images matter: public datasets rarely contain your lab, your lighting and your
camera, and the examiner will ask what data *you* collected.

    python -m model.collect_frames --out data/raw/candle_lab --every 1.0     # auto-save 1 frame/s
    python -m model.collect_frames --source fire_video.mp4 --out data/raw/video01 --every 0.5
    python -m model.collect_frames --manual --out data/raw/negatives          # press SPACE to save

Collect NEGATIVES too (red clothes, sunset, tube lights, orange walls, phone torch): they teach
the model what is *not* fire and are the main cure for false alarms.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="0")
    p.add_argument("--out", required=True)
    p.add_argument("--every", type=float, default=1.0, help="seconds between automatic saves")
    p.add_argument("--manual", action="store_true", help="only save when SPACE is pressed")
    p.add_argument("--max", type=int, default=2000)
    args = p.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.source}")

    is_file = not isinstance(source, int)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    saved, last, frame_no = 0, 0.0, 0
    while saved < args.max:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        t = frame_no / fps if is_file else time.time()
        key = cv2.waitKey(1) & 0xFF
        want = (key == ord(" ")) if args.manual else (t - last >= args.every)
        if want:
            cv2.imwrite(str(out / f"{out.name}_{int(time.time() * 1000)}.jpg"), frame)
            saved, last = saved + 1, t
        view = frame.copy()
        cv2.putText(view, f"saved {saved}  (q quit{', SPACE save' if args.manual else ''})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("collect", view)
        if key == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    print(f"saved {saved} images to {out}")


if __name__ == "__main__":
    main()
