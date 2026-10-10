"""Download the public datasets used for the baseline model and build datasets/fire (Tanishka).

    python -m model.download_public_datasets            # -> data/public/... and datasets/fire/data.yaml
    python -m model.download_public_datasets --extra data/labelled/own   # also merge your own labelled images

Sources (all free to use with attribution - cite them in the report):
  1. "fire" v8 by Roboflow user custom-thxhn, CCTV fire + smoke, YOLO format, CC BY 4.0
     https://universe.roboflow.com/custom-thxhn/fire-wrpgm  (copy taken from
     github.com/Abonia1/YOLOv8-Fire-and-Smoke-Detection, datasets/fire-8)
     Its "default" class is an image-level tag on normal CCTV scenes; it is dropped, so those
     images become negatives.
  2. FireNET by Moses Olafenwa, 502 fire images, Pascal-VOC boxes, MIT licence
     https://github.com/OlafenwaMoses/FireNET
  3. COCO128 (first 128 COCO train2017 images, Ultralytics), used ONLY as negatives (no fire).
     One image with a lit candle (000000000078.jpg) is removed.

Requires git and internet access. Uses about 60 MB.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from common.config import PROJECT_ROOT

from . import prepare_dataset, voc_to_yolo

FIRE8_REPO = "https://github.com/Abonia1/YOLOv8-Fire-and-Smoke-Detection"
FIRENET_URL = "https://github.com/OlafenwaMoses/FireNET/releases/download/v1.0/fire-dataset.zip"
COCO128_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip"
COCO_EXCLUDE = {"000000000078.jpg"}   # contains a lit candle - not a valid negative


def download(url: str, dest: Path) -> Path:
    if not dest.exists():
        print(f"downloading {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
    return dest


def get_fire8(root: Path) -> Path:
    repo = root / "fire8_repo"
    if not repo.exists():
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", FIRE8_REPO, str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", "datasets/fire-8"], check=True)
    return repo / "datasets" / "fire-8"


def get_firenet(root: Path) -> Path:
    out = root / "firenet_yolo"
    if out.exists():
        return out
    z = download(FIRENET_URL, root / "fire-dataset.zip")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(root / "firenet_raw")
    base = root / "firenet_raw" / "fire-dataset"
    for split in ("train", "validation"):
        voc_to_yolo.main(["--images", str(base / split / "images"), "--annotations", str(base / split / "annotations"),
                          "--out", str(out), "--prefix", f"firenet_{split}_"])
    return out


def get_coco_negatives(root: Path) -> Path:
    out = root / "coco_negatives"
    if out.exists():
        return out
    z = download(COCO128_URL, root / "coco128.zip")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(root / "coco_raw")
    out.mkdir(parents=True)
    for img in (root / "coco_raw" / "coco128" / "images" / "train2017").glob("*.jpg"):
        if img.name not in COCO_EXCLUDE:
            shutil.copy2(img, out / img.name)   # images only: COCO labels (person, car...) must not be used
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(PROJECT_ROOT / "data" / "public"))
    p.add_argument("--out", default=str(PROJECT_ROOT / "datasets" / "fire"))
    p.add_argument("--extra", nargs="*", default=[], help="more YOLO-format folders to merge (your own data)")
    args = p.parse_args(argv)
    root = Path(args.root)
    inputs = [get_fire8(root), get_firenet(root), get_coco_negatives(root), *map(Path, args.extra)]
    prepare_dataset.main(["--inputs", *map(str, inputs), "--out", args.out,
                          "--classes", "fire", "smoke", "--class-map", "Fire=fire"])


if __name__ == "__main__":
    main()
