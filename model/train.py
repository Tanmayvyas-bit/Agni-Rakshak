"""Train YOLOv8 for fire + smoke detection (Tanishka).

    python -m model.train --data datasets/fire/data.yaml                 # yolov8n, 100 epochs
    python -m model.train --data datasets/fire/data.yaml --model yolov8s.pt --epochs 150 --batch 32
    python -m model.train --resume runs/fire/yolov8n_fire/weights/last.pt

No GPU on the laptop? Use model/train_colab.ipynb on Google Colab (free T4 GPU).
After training, the best weights are copied to model/weights/best.pt, which every other part
of the project (webcam script, dashboard, GUI) picks up automatically.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="datasets/fire/data.yaml")
    p.add_argument("--model", default="yolov8n.pt", help="yolov8n.pt (fast, Pi-friendly) or yolov8s.pt (more accurate)")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16, help="lower to 8 if you run out of GPU memory")
    p.add_argument("--patience", type=int, default=25, help="stop early if val mAP doesn't improve")
    p.add_argument("--device", default=None, help="0 for GPU, cpu, or mps (Apple)")
    p.add_argument("--name", default=None)
    p.add_argument("--resume", help="path to last.pt to continue an interrupted run")
    args = p.parse_args(argv)

    from ultralytics import YOLO

    if args.resume:
        model = YOLO(args.resume)
        model.train(resume=True)
    else:
        model = YOLO(args.model)
        name = args.name or f"{Path(args.model).stem}_fire"
        model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            patience=args.patience,
            device=args.device,
            project=str(ROOT / "runs" / "fire"),
            name=name,
            exist_ok=True,
            # augmentation tuned for fire: colour shifts must stay small or flames stop looking like flames
            hsv_h=0.010, hsv_s=0.6, hsv_v=0.4,
            fliplr=0.5, mosaic=1.0, mixup=0.1, degrees=5.0, scale=0.5,
            plots=True,
        )

    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    target = ROOT / "model" / "weights" / "best.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, target)
    print(f"\nbest weights copied to {target}")
    print(f"training plots (loss curves, confusion matrix, PR curve): {model.trainer.save_dir}")


if __name__ == "__main__":
    main()
