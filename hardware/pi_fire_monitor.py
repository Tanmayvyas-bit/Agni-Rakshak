"""Raspberry Pi 4 fire monitor: Pi camera + YOLOv8 + DHT22 + MQ-2 -> LEDs/buzzer + dashboard (Tanmay).

On the Pi:
    python -m hardware.pi_fire_monitor                       # Pi camera module + real sensors
    python -m hardware.pi_fire_monitor --camera usb          # USB webcam instead of the CSI camera
    python -m hardware.pi_fire_monitor --no-camera           # sensors only
On a laptop (no hardware yet):
    python -m hardware.pi_fire_monitor --simulate --camera usb    # webcam + simulated sensors
    python -m hardware.pi_fire_monitor --simulate --no-camera     # simulated sensors only
"""
from __future__ import annotations

import argparse
import logging
import signal
import socket
import time

from common.alerts import AlertTracker
from common.config import load_config, resolve
from common.dashboard_client import DashboardClient
from common.detector import FireDetector, annotate, best_confidence
from common.fusion import SAFE, Reading, assess

from .sensors import SensorHub

log = logging.getLogger("pi_monitor")


class Camera:
    def __init__(self, kind: str, width=640, height=480):
        self.kind = kind
        if kind == "picamera":
            from picamera2 import Picamera2

            self._cam = Picamera2()
            self._cam.configure(self._cam.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"}))   # RGB888 in libcamera = BGR byte order for OpenCV
            self._cam.start()
            time.sleep(1)
        else:
            import cv2

            self._cam = cv2.VideoCapture(0)
            self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def read(self):
        if self.kind == "picamera":
            return self._cam.capture_array()
        ok, frame = self._cam.read()
        return frame if ok else None

    def close(self):
        if self.kind == "picamera":
            self._cam.stop()
        else:
            self._cam.release()


def main(argv=None):
    cfg = load_config()
    p = argparse.ArgumentParser()
    p.add_argument("--simulate", action="store_true", help="fake sensor values (no GPIO needed)")
    p.add_argument("--camera", choices=["picamera", "usb"], default="picamera")
    p.add_argument("--no-camera", action="store_true")
    p.add_argument("--weights", default=cfg["model"]["pi_weights"])
    p.add_argument("--imgsz", type=int, default=320)
    p.add_argument("--device-id", default=f"pi-{socket.gethostname()}")
    p.add_argument("--dashboard", default=cfg["dashboard"]["url"], help="e.g. http://192.168.1.20:5000")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    hub = SensorHub(cfg, simulate=args.simulate)
    camera = detector = None
    if not args.no_camera:
        weights = resolve(args.weights)
        if not weights.exists() and resolve(cfg["model"]["weights"]).exists():
            weights = resolve(cfg["model"]["weights"])   # fall back to the .pt if NCNN wasn't exported yet
        detector = FireDetector(weights, conf=cfg["model"]["conf"], iou=cfg["model"]["iou"], imgsz=args.imgsz,
                                allow_demo=cfg["model"]["allow_demo_detector"])
        camera = Camera(args.camera)
        log.info("camera %s, detector %s", args.camera, detector.mode)

    client = DashboardClient(args.dashboard, cfg["dashboard"]["api_key"], args.device_id, kind="raspberry-pi")
    tracker = AlertTracker(cfg["alerts"]["min_consecutive_frames"] if camera else 2, cfg["alerts"]["cooldown_seconds"])
    interval = cfg["sensors"]["read_interval_seconds"]

    running = True

    def _stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    snap = hub.read()
    last_sensor = last_frame_sent = 0.0
    try:
        while running:
            now = time.time()
            if now - last_sensor >= interval:
                snap = hub.read()
                last_sensor = now

            dets, frame = [], None
            if camera:
                frame = camera.read()
                if frame is not None:
                    dets = detector.detect(frame)
            fire, smoke_c = best_confidence(dets, "fire"), best_confidence(dets, "smoke")
            result = assess(Reading(fire, smoke_c, snap.temperature, snap.smoke_pct, snap.smoke_digital), cfg["fusion"])
            hub.indicators.show(result.level)

            shown = annotate(frame, dets, detector.mode, result.level) if frame is not None else None
            if last_sensor == now:   # once per sensor interval: push the reading to the dashboard
                client.send_reading(temperature=snap.temperature, humidity=snap.humidity, smoke=snap.smoke_pct,
                                    smoke_digital=snap.smoke_digital, fire_conf=fire, smoke_conf=smoke_c)
                log.info("T=%s°C H=%s%% smoke=%s%% DO=%s cam=%.2f -> %s (%d)", snap.temperature, snap.humidity,
                         snap.smoke_pct, snap.smoke_digital, fire, result.level, result.score)
            if shown is not None and now - last_frame_sent >= 1.0:
                client.send_frame(shown)
                last_frame_sent = now
            if tracker.update(result.level != SAFE):
                label = "fire" if fire > 0 else "smoke" if smoke_c > 0 else "sensor"
                log.warning("ALERT %s: %s", result.level, "; ".join(result.reasons))
                client.send_event(result.level, label, max(fire, smoke_c), shown, score=result.score,
                                  reasons=result.reasons, temperature=snap.temperature, smoke=snap.smoke_pct,
                                  detector_mode=detector.mode if detector else "sensors")
            if not camera:
                time.sleep(interval)
    finally:
        hub.indicators.off()
        if camera:
            camera.close()
        log.info("stopped")


if __name__ == "__main__":
    main()
