"""Export the trained model for the Raspberry Pi 4 (month 2-3).

PyTorch .pt runs at ~1 FPS on a Pi 4; NCNN at imgsz 320 runs at roughly 5-8 FPS.

    python -m model.export --weights model/weights/best.pt --format ncnn --imgsz 320
    python -m model.export --format onnx
"""
from __future__ import annotations

import argparse


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default="model/weights/best.pt")
    p.add_argument("--format", default="ncnn", choices=["ncnn", "onnx", "tflite", "openvino"])
    p.add_argument("--imgsz", type=int, default=320)
    args = p.parse_args(argv)

    from ultralytics import YOLO

    path = YOLO(args.weights).export(format=args.format, imgsz=args.imgsz, half=False)
    print(f"exported to {path}  - copy this to the Pi at model/weights/")


if __name__ == "__main__":
    main()
