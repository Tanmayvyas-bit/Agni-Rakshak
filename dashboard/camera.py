"""Runs the laptop webcam + YOLOv8 inside the dashboard server, so the browser can watch it live."""
from __future__ import annotations

import logging
import threading
import time

import cv2

from common.alerts import AlertTracker
from common.detector import FireDetector, annotate, best_confidence
from common.fusion import Reading, assess

log = logging.getLogger(__name__)


class CameraWorker:
    def __init__(self, cfg: dict, detector_factory, on_alert):
        self.cfg = cfg
        self._detector_factory = detector_factory
        self._on_alert = on_alert          # callback(level, label, confidence, frame, assessment, mode)
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._jpeg = None
        self.fps = 0.0
        self.error = None
        self.mode = None
        self.last_level = "SAFE"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, source=None) -> None:
        if self.running:
            return
        self._stop.clear()
        self.error = None
        src = self.cfg["camera"]["source"] if source is None else source
        self._thread = threading.Thread(target=self._loop, args=(src,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        with self._lock:
            self._jpeg = None

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def _loop(self, source) -> None:
        try:
            detector: FireDetector = self._detector_factory()
            self.mode = detector.mode
        except Exception as exc:   # noqa: BLE001 - show any model loading error in the UI
            self.error = f"model failed to load: {exc}"
            log.exception("model load failed")
            return
        cap = cv2.VideoCapture(int(source) if str(source).isdigit() else source)
        if not cap.isOpened():
            self.error = f"cannot open camera {source!r}"
            return
        is_file = not str(source).isdigit() and not str(source).startswith(("rtsp:", "http:", "https:"))
        frame_gap = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if is_file else 0.0   # play files at real speed
        tracker = AlertTracker(self.cfg["alerts"]["min_consecutive_frames"], self.cfg["alerts"]["cooldown_seconds"])
        last = time.time()
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    self.error = "video finished" if is_file else "camera stopped sending frames"
                    break
                if frame_gap:
                    time.sleep(max(0.0, frame_gap - (time.time() - last)))
                dets = detector.detect(frame)
                fire, smoke = best_confidence(dets, "fire"), best_confidence(dets, "smoke")
                result = assess(Reading(fire_conf=fire, smoke_conf=smoke), self.cfg["fusion"])
                self.last_level = result.level
                now = time.time()
                self.fps = 0.9 * self.fps + 0.1 / max(now - last, 1e-6)
                last = now
                shown = annotate(frame, dets, detector.mode, result.level, self.fps)
                ok, buf = cv2.imencode(".jpg", shown, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ok:
                    with self._lock:
                        self._jpeg = buf.tobytes()
                if tracker.update(fire > 0 or smoke > 0):
                    self._on_alert(result.level, "fire" if fire >= smoke else "smoke", max(fire, smoke),
                                   shown, result, detector.mode)
        finally:
            cap.release()
