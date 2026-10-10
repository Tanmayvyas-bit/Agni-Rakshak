"""Evaluate the trained model on the held-out TEST split and write a report for the documentation.

    python -m model.evaluate --weights model/weights/best.pt --data datasets/fire/data.yaml

Writes docs/results/model_metrics.md (paste into the project report) and model_metrics.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default="model/weights/best.pt")
    p.add_argument("--data", default="datasets/fire/data.yaml")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--split", default="test")
    p.add_argument("--out", default="docs/results")
    args = p.parse_args(argv)

    from ultralytics import YOLO

    model = YOLO(args.weights)
    m = model.val(data=args.data, split=args.split, imgsz=args.imgsz, plots=True,
                  project=str(ROOT / "runs" / "fire"), name="eval", exist_ok=True)

    per_class = {}
    for i, cls_idx in enumerate(m.box.ap_class_index):
        name = m.names[int(cls_idx)]
        p_, r_, ap50, ap = m.box.class_result(i)
        per_class[name] = {"precision": round(float(p_), 4), "recall": round(float(r_), 4),
                           "mAP50": round(float(ap50), 4), "mAP50-95": round(float(ap), 4)}

    speed = m.speed  # ms per image: preprocess / inference / postprocess
    report = {
        "weights": args.weights, "split": args.split, "imgsz": args.imgsz,
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M"),
        "precision": round(float(m.box.mp), 4), "recall": round(float(m.box.mr), 4),
        "mAP50": round(float(m.box.map50), 4), "mAP50-95": round(float(m.box.map), 4),
        "inference_ms": round(float(speed.get("inference", 0)), 2), "per_class": per_class,
    }

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "model_metrics.json").write_text(json.dumps(report, indent=2))
    lines = [
        f"# Model evaluation ({report['evaluated_at']})", "",
        f"Weights: `{args.weights}` | split: **{args.split}** | image size: {args.imgsz}", "",
        "| Class | Precision | Recall | mAP@50 | mAP@50-95 |", "|---|---|---|---|---|",
        f"| **all** | {report['precision']:.3f} | {report['recall']:.3f} | {report['mAP50']:.3f} | {report['mAP50-95']:.3f} |",
    ]
    for name, v in per_class.items():
        lines.append(f"| {name} | {v['precision']:.3f} | {v['recall']:.3f} | {v['mAP50']:.3f} | {v['mAP50-95']:.3f} |")
    lines += ["", f"Inference time: {report['inference_ms']} ms / image on this machine.",
              f"Plots (confusion matrix, PR curve): `{m.save_dir}`"]
    (out / "model_metrics.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
