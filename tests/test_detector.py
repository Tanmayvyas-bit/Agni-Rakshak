import cv2
import numpy as np

from common.detector import ColorFireDetector, FireDetector, annotate


def test_falls_back_to_demo_when_no_weights(tmp_path):
    d = FireDetector(tmp_path / "missing.pt")
    assert d.mode == "demo"


def test_demo_detector_finds_flame_coloured_blob_and_ignores_dark_frame():
    frame = np.zeros((480, 640, 3), np.uint8)
    assert ColorFireDetector().detect(frame) == []
    cv2.circle(frame, (320, 240), 60, (0, 160, 255), -1)   # bright orange (BGR)
    dets = ColorFireDetector().detect(frame)
    assert len(dets) == 1 and dets[0].label == "fire"
    x1, y1, x2, y2 = dets[0].box
    assert x1 < 320 < x2 and y1 < 240 < y2
    out = annotate(frame, dets, "demo", "FIRE", 12.0)
    assert out.shape == frame.shape
