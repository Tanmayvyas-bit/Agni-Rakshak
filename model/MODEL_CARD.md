# Trained model: YOLOv8n fire + smoke (v1 baseline)

`model/weights/best.pt` - trained by the team's training pipeline (`model/train.py`) on CPU.

## Results on the held-out TEST split (never used for training or tuning)

| Class | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---|---|---|---|
| all | 0.849 | 0.767 | 0.825 | 0.388 |
| fire | 0.774 | 0.691 | 0.718 | 0.331 |
| smoke | 0.924 | 0.843 | 0.932 | 0.445 |

Training ran 60 epochs; best validation mAP@50 = 0.877 at epoch 54.
Plots: `docs/results/training/` (loss curves, confusion matrix, PR curve, sample predictions).

## Training setup

| Setting | Value |
|---|---|
| Base model | yolov8n.pt (COCO pretrained) |
| Image size | 416 |
| Epochs | 60 (early-stop patience 20) |
| Batch | 16 |
| Device | CPU (4 cores) |
| Classes | 0 fire, 1 smoke |

## Data (1,588 images; rebuild with `python -m model.download_public_datasets`)

| Source | Images | Licence |
|---|---|---|
| Roboflow `fire` v8 (custom-thxhn), CCTV fire + smoke | 979 (`default` image tags dropped -> negatives) | CC BY 4.0 |
| FireNET (Moses Olafenwa), fire only | 502 | MIT |
| COCO128 images, negatives only (1 candle image removed) | 127 | COCO terms |

Split 70/20/10 by source group (video frames and augmented copies never cross splits); 20 duplicates removed.

## Known limitations (fix in month 2)

* FireNET labels only fire, so its visible smoke counts as background - smoke recall is weaker than fire.
* Few small/indoor fires (candle, lighter) and no team-collected images yet - collect them with `model/collect_frames.py`.
* Few hard negatives (sunsets, red clothes, lamps): expect some false alarms; keep the N-frame rule on.
* Trained at 416 px on CPU for 60 epochs; a GPU run (Colab) at 640 px / 100+ epochs should score higher.
* This is a baseline for the month-1 demo, not a certified fire alarm.
