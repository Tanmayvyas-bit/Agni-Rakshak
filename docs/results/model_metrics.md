# Model evaluation (2026-10-10 08:10)

Weights: `model/weights/best.pt` | split: **test** | image size: 416

| Class | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---|---|---|---|
| **all** | 0.849 | 0.767 | 0.825 | 0.388 |
| fire | 0.774 | 0.691 | 0.718 | 0.331 |
| smoke | 0.924 | 0.843 | 0.932 | 0.445 |

Inference time: 29.95 ms / image on this machine.
Plots (confusion matrix, PR curve): `/home/user/agni-rakshak/runs/fire/eval`
