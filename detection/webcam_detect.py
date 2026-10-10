"""Month-1 deliverable: real-time fire detection from the laptop webcam with YOLOv8.

Run from the project root:
    python -m detection.webcam_detect                      # webcam 0, weights from config.yaml
    python -m detection.webcam_detect --source test.mp4    # a video file
    python -m detection.webcam_detect --weights model/weights/best.pt --conf 0.5
    python -m detection.webcam_detect --no-dashboard       # run without the web dashboard

Keys while running:  q = quit,  s = save snapshot,  p = pause
"""
from __future__ import annotations

import argparse
import logging
import socket
import time
from datetime import datetime

import cv2

from common.alerts import AlertTracker, beep
from common.config import load_config, resolve
from common.dashboard_client import DashboardClient
from common.detector import FireDetector, annotate, best_confidence
from common.fusion import Reading, assess

log = logging.getLogger("webcam_detect")


def parse_source(value):
    return int(value) if str(value).isdigit() else value


def main(argv=None):
    cfg = load_config()
    p = argparse.ArgumentParser(description="YOLOv8 fire detection on the laptop webcam")
    p.add_argument("--source", default=cfg["camera"]["source"], help="camera index, video file or RTSP URL")
    p.add_argument("--weights", default=cfg["model"]["weights"])
    p.add_argument("--conf", type=float, default=cfg["model"]["conf"])
    p.add_argument("--imgsz", type=int, default=cfg["model"]["imgsz"])
    p.add_argument("--no-dashboard", action="store_true", help="don't send events to the web dashboard")
    p.add_argument("--no-sound", action="store_true")
    p.add_argument("--save-video", help="write the annotated video to this .mp4 file")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    detector = FireDetector(resolve(args.weights), conf=args.conf, iou=cfg["model"]["iou"], imgsz=args.imgsz,
                            allow_demo=cfg["model"]["allow_demo_detector"])
    log.info("detector mode: %s", detector.mode)
    tracker = AlertTracker(cfg["alerts"]["min_consecutive_frames"], cfg["alerts"]["cooldown_seconds"])
    client = None if args.no_dashboard else DashboardClient(
        cfg["dashboard"]["url"], cfg["dashboard"]["api_key"], device_id=f"laptop-{socket.gethostname()}")

    snap_dir = resolve(cfg["alerts"]["snapshot_dir"])
    snap_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(parse_source(args.source))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["camera"]["width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["camera"]["height"])
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera/video source {args.source!r}")

    writer = None
    fps, last, paused, frame_no = 0.0, time.time(), False, 0
    while True:
        if not paused:
            ok, frame = cap.read()
            if not ok:
                log.info("end of stream")
                break
            frame_no += 1
            detections = detector.detect(frame)
            fire = best_confidence(detections, "fire")
            smoke = best_confidence(detections, "smoke")
            result = assess(Reading(fire_conf=fire, smoke_conf=smoke), cfg["fusion"])

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
            last = now
            shown = annotate(frame, detections, detector.mode, result.level, fps)

            if tracker.update(fire > 0 or smoke > 0):
                path = snap_dir / f"alert_{datetime.now():%Y%m%d_%H%M%S}.jpg"
                cv2.imwrite(str(path), shown)
                log.warning("ALERT %s fire=%.2f smoke=%.2f -> %s", result.level, fire, smoke, path.name)
                if not args.no_sound and cfg["alerts"]["sound"]:
                    beep()
                if client:
                    client.send_event(result.level, "fire" if fire >= smoke else "smoke", max(fire, smoke), shown,
                                      score=result.score, reasons=result.reasons, detector_mode=detector.mode)
            if client and frame_no % 15 == 0:   # ~1-2 preview frames per second to the dashboard
                client.send_frame(shown)

            if args.save_video:
                if writer is None:
                    h, w = shown.shape[:2]
                    writer = cv2.VideoWriter(args.save_video, cv2.VideoWriter_fourcc(*"mp4v"), 20, (w, h))
                writer.write(shown)
            cv2.imshow("Smart Fire Detection - laptop camera (q to quit)", shown)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("p"):
            paused = not paused
        if key == ord("s"):
            path = snap_dir / f"manual_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            cv2.imwrite(str(path), shown)
            log.info("saved %s", path)

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
