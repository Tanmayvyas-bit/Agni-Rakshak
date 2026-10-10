"""One detector class used by the laptop script, the dashboard, the GUI and the Raspberry Pi.

* If trained YOLOv8 weights exist (model/weights/best.pt) they are used.
* If not, a simple colour-based DEMO detector is used so the dashboard, the GUI and the hardware
  can be built and tested in week 1 while Tanishka is still training the real model.
  The demo detector is clearly labelled on screen and should NEVER be used in the final evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

COLORS = {"fire": (0, 69, 255), "smoke": (160, 160, 160)}   # BGR


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]   # x1, y1, x2, y2 in pixels

    def to_dict(self) -> dict:
        return {"label": self.label, "confidence": round(self.confidence, 3), "box": list(self.box)}


class ColorFireDetector:
    """Finds bright orange/yellow flame-coloured blobs. Week-1 placeholder only."""

    mode = "demo"

    def __init__(self, conf: float = 0.45, min_area_ratio: float = 0.002):
        self.conf = conf
        self.min_area_ratio = min_area_ratio

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # flame: red-orange-yellow hue, saturated and very bright
        mask = cv2.inRange(hsv, (0, 120, 200), (35, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area_ratio * w * h:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            fill = area / float(bw * bh)
            confidence = float(min(0.95, 0.4 + fill * 0.6))
            if confidence >= self.conf:
                out.append(Detection("fire", confidence, (x, y, x + bw, y + bh)))
        return out


class YoloFireDetector:
    mode = "yolo"

    def __init__(self, weights: str | Path, conf: float = 0.45, iou: float = 0.5, imgsz: int = 640):
        from ultralytics import YOLO   # imported here so the demo mode works without ultralytics

        self.model = YOLO(str(weights), task="detect")
        self.conf, self.iou, self.imgsz = conf, iou, imgsz

    def detect(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.predict(frame, conf=self.conf, iou=self.iou, imgsz=self.imgsz, verbose=False)[0]
        names = result.names
        out = []
        for box in result.boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            out.append(Detection(str(names[int(box.cls)]).lower(), float(box.conf), (x1, y1, x2, y2)))
        return out


class FireDetector:
    """Facade: picks YOLO when weights are available, otherwise the demo detector."""

    def __init__(self, weights: str | Path | None = None, conf: float = 0.45, iou: float = 0.5,
                 imgsz: int = 640, allow_demo: bool = True):
        self.conf = conf
        weights_path = Path(weights) if weights else None
        if weights_path is not None and weights_path.exists():
            self._impl = YoloFireDetector(weights_path, conf=conf, iou=iou, imgsz=imgsz)
        elif allow_demo:
            self._impl = ColorFireDetector(conf=conf)
        else:
            raise FileNotFoundError(f"Model weights not found: {weights}. Train the model first (model/train.py).")

    @property
    def mode(self) -> str:
        return self._impl.mode

    def set_conf(self, conf: float) -> None:
        self.conf = self._impl.conf = conf

    def detect(self, frame: np.ndarray) -> list[Detection]:
        return self._impl.detect(frame)


def best_confidence(detections: list[Detection], label: str) -> float:
    return max((d.confidence for d in detections if d.label == label), default=0.0)


def annotate(frame: np.ndarray, detections: list[Detection], mode: str = "yolo",
             status: str | None = None, fps: float | None = None) -> np.ndarray:
    """Draw boxes, labels and a status bar on a copy of the frame."""
    img = frame.copy()
    for d in detections:
        color = COLORS.get(d.label, (0, 255, 255))
        x1, y1, x2, y2 = d.box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        text = f"{d.label} {d.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(img, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
        cv2.putText(img, text, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    bar = []
    if status:
        bar.append(status)
    if fps is not None:
        bar.append(f"{fps:.1f} FPS")
    if mode == "demo":
        bar.append("DEMO DETECTOR (no trained model)")
    if bar:
        bar_color = {"FIRE": (0, 0, 220), "WARNING": (0, 140, 255)}.get(status, (40, 40, 40))
        cv2.rectangle(img, (0, 0), (img.shape[1], 32), bar_color, -1)
        cv2.putText(img, "  |  ".join(bar), (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return img
