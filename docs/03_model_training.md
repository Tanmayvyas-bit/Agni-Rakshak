# 3. Data collection and YOLOv8 training: Tanishka Yadav

## 3.1 Classes

| id | class | what to box |
|---|---|---|
| 0 | `fire` | Visible flames, including small ones (candle, lighter). Box the flame, not the object burning. |
| 1 | `smoke` | Visible smoke plumes. Box the dense part; skip thin haze you cannot outline. |

Images with **no** fire/smoke (empty label file) are **negatives**. Keep 15–20 % of the dataset as negatives:
red/orange clothes, sunsets, tube lights, bulbs, orange walls, car tail lights, fog/steam, cooking vapour.

## 3.2 Where the data comes from

1. **Public datasets.** Roboflow Universe (search "fire smoke"), the D-Fire dataset (~21k images, fire + smoke,
   YOLO format) and Kaggle fire datasets. Download in **YOLOv8** format. Check each dataset's licence and cite it in the report.
2. **Own images** (examiners always ask about this):
   ```bash
   python -m model.collect_frames --out data/raw/candle_lab --every 1.0
   python -m model.collect_frames --source bonfire.mp4 --out data/raw/bonfire_vid --every 0.5
   python -m model.collect_frames --manual --out data/raw/negatives      # SPACE saves a frame
   ```
   Vary distance (0.5–5 m), lighting (day, night, tube light), angle, background and camera (laptop, phone, Pi camera).
3. **Label** the own images in Roboflow, Label Studio or makesense.ai and export in **YOLO** format.

Target for month 1: **≥ 3,000 images** total (≥ 300 own images, ≥ 500 negatives).

## 3.3 Build the dataset

```bash
python -m model.prepare_dataset \
    --inputs data/downloads/dfire data/downloads/roboflow_fire data/labelled/own \
    --out datasets/fire --classes fire smoke --class-map "Fire=fire" "flame=fire" "Smoke=smoke"
```
The tool:
* reads each source's `data.yaml`/`classes.txt` and **remaps class names** to `fire`, `smoke` (other classes are dropped),
* **checks every label** (5 values, class in range, box normalised 0–1) and skips broken files,
* **removes duplicate images** (MD5 hash), which matters when public datasets overlap,
* shuffles with a fixed seed and splits **70 % train / 20 % val / 10 % test**,
* writes `datasets/fire/data.yaml` and prints boxes per class and negatives per split. Put these numbers in the report.

> The **test** split is never used for training or tuning. Report final numbers on it only.

## 3.4 Train

Most laptops have no NVIDIA GPU. Use **Google Colab** with `model/train_colab.ipynb` (Runtime → T4 GPU).
On a laptop with an NVIDIA GPU:
```bash
python -m model.train --data datasets/fire/data.yaml --model yolov8n.pt --epochs 100 --batch 16
python -m model.train --data datasets/fire/data.yaml --model yolov8s.pt --epochs 100 --batch 16   # comparison
```
Settings and why:

| Setting | Value | Reason |
|---|---|---|
| model | yolov8n (3.2 M params) | Fast enough for the Raspberry Pi. Compare with yolov8s (11.2 M) |
| imgsz | 640 | Standard. The Pi uses 320 after export |
| epochs / patience | 100 / 25 | Early stopping when val mAP stops improving |
| hsv_h | 0.010 (default 0.015) | Large hue shifts make flames blue/green, which is unrealistic |
| mosaic, mixup | 1.0, 0.1 | Helps small, far-away fires |
| fliplr, degrees, scale | 0.5, 5, 0.5 | Camera may be tilted; fires appear at many sizes |

The best weights are copied automatically to `model/weights/best.pt`. Every other part of the project then uses them.

## 3.5 Evaluate

```bash
python -m model.evaluate --weights model/weights/best.pt --data datasets/fire/data.yaml
```
This writes `docs/results/model_metrics.md` (precision, recall, mAP@50, mAP@50-95 per class, inference time).
Plots (confusion matrix, PR curve, loss curves) are saved under `runs/fire/`.

| Metric | Meaning | Month-1 target | Final target |
|---|---|---|---|
| mAP@50 | Average precision at IoU 0.5 | ≥ 0.75 | ≥ 0.80 |
| Recall (fire) | Share of real fires found. **Most important for safety** | ≥ 0.80 | ≥ 0.90 |
| Precision (fire) | Share of detections that are real fires (false-alarm control) | ≥ 0.75 | ≥ 0.85 |

Also run the live webcam test in [07](07_testing_and_evaluation.md).

## 3.6 Test live on the webcam

```bash
python -m detection.webcam_detect --conf 0.45          # q quit · s snapshot · p pause
python -m detection.webcam_detect --source fire_test.mp4 --save-video outputs/demo.mp4
```

## 3.7 Export for the Raspberry Pi (month 2–3)

```bash
python -m model.export --format ncnn --imgsz 320     # -> model/weights/best_ncnn_model/
```

## 3.8 Improving the model (month 2 onwards)

* Look at **false positives** (what did it think was fire?). Add more of those as negatives.
* Look at **false negatives** (missed fires: small, far, smoky, at night?). Collect more of those.
* Try yolov8s and imgsz 800 for small fires, and compare speed vs accuracy.
* Tune `conf` with the PR curve: choose the threshold that keeps fire recall ≥ 0.9.
