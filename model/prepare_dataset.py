"""Merge labelled datasets, check every label, remove duplicates and split into train/val/test.

Input: one or more folders exported in **YOLO format** (from Roboflow, Label Studio, CVAT or
makesense.ai). Each folder may be flat (images + .txt side by side) or have images/ and labels/
sub-folders, optionally further split into train/valid/test (those are re-split here).

    python -m model.prepare_dataset --inputs data/downloads/dfire data/labelled/our_lab \
        --out datasets/fire --classes fire smoke --class-map "Fire=fire" "smoke=smoke"

Writes datasets/fire/{images,labels}/{train,val,test} and datasets/fire/data.yaml.
Images with no objects (empty .txt) are kept: they are the negatives.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import shutil
from collections import Counter
from pathlib import Path

import yaml

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def find_pairs(folder: Path):
    """Yield (image, label_or_None) for every image under folder."""
    for img in sorted(folder.rglob("*")):
        if img.suffix.lower() not in IMG_EXT:
            continue
        candidates = [img.with_suffix(".txt")]
        parts = list(img.parts)
        if "images" in parts:   # .../images/train/x.jpg -> .../labels/train/x.txt
            i = len(parts) - 1 - parts[::-1].index("images")
            candidates.append(Path(*parts[:i], "labels", *parts[i + 1:]).with_suffix(".txt"))
        label = next((c for c in candidates if c.exists()), None)
        yield img, label


def read_source_names(folder: Path) -> list[str] | None:
    for name in ("data.yaml", "data.yml"):
        f = folder / name
        if f.exists():
            names = (yaml.safe_load(f.read_text()) or {}).get("names")
            if isinstance(names, dict):
                return [names[k] for k in sorted(names)]
            return names
    classes = folder / "classes.txt"
    if classes.exists():
        return [c.strip() for c in classes.read_text().splitlines() if c.strip()]
    return None


def check_label_lines(lines: list[str], n_src_classes: int | None) -> list[str]:
    """Return a list of problems in a YOLO label file (empty list = file is fine)."""
    problems = []
    for i, line in enumerate(lines, 1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5:
            problems.append(f"line {i}: expected 5 values, got {len(parts)}")
            continue
        try:
            cls = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:])
        except ValueError:
            problems.append(f"line {i}: not numbers")
            continue
        if cls < 0 or (n_src_classes is not None and cls >= n_src_classes):
            problems.append(f"line {i}: class id {cls} out of range")
        if not all(0.0 <= v <= 1.0 for v in (x, y, w, h)) or w == 0 or h == 0:
            problems.append(f"line {i}: box not normalised to 0-1")
    return problems


def remap_lines(lines, src_names, class_map, out_classes):
    """Translate class ids from the source dataset's names to our class list; drop unknown classes."""
    out = []
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(float(parts[0]))
        name = src_names[cls] if src_names and cls < len(src_names) else out_classes[cls] if cls < len(out_classes) else None
        name = class_map.get(name, name)
        if name in out_classes:
            out.append(" ".join([str(out_classes.index(name))] + parts[1:]))
    return out


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", nargs="+", required=True)
    p.add_argument("--out", default="datasets/fire")
    p.add_argument("--classes", nargs="+", default=["fire", "smoke"])
    p.add_argument("--class-map", nargs="*", default=[], help='rename source classes, e.g. "Fire=fire" "flame=fire"')
    p.add_argument("--split", nargs=3, type=float, default=[0.7, 0.2, 0.1], metavar=("TRAIN", "VAL", "TEST"))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    class_map = dict(item.split("=", 1) for item in args.class_map)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)

    items, seen, stats = [], set(), Counter()
    for folder in map(Path, args.inputs):
        src_names = read_source_names(folder)
        for img, label in find_pairs(folder):
            h = file_hash(img)
            if h in seen:
                stats["duplicates_skipped"] += 1
                continue
            seen.add(h)
            lines = label.read_text().splitlines() if label else []
            problems = check_label_lines(lines, len(src_names) if src_names else None)
            if problems:
                stats["bad_labels_skipped"] += 1
                print(f"skip {img}: {problems[0]}")
                continue
            lines = remap_lines(lines, src_names, class_map, args.classes)
            items.append((img, lines))

    random.Random(args.seed).shuffle(items)
    n = len(items)
    n_train, n_val = int(n * args.split[0]), int(n * args.split[1])
    splits = {"train": items[:n_train], "val": items[n_train:n_train + n_val], "test": items[n_train + n_val:]}

    box_counts = Counter()
    for split, rows in splits.items():
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        for idx, (img, lines) in enumerate(rows):
            stem = f"{split}_{idx:06d}"
            shutil.copy2(img, out / "images" / split / f"{stem}{img.suffix.lower()}")
            (out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
            if not lines:
                stats[f"{split}_negatives"] += 1
            for line in lines:
                box_counts[args.classes[int(line.split()[0])]] += 1

    data_yaml = {"path": str(out.resolve()), "train": "images/train", "val": "images/val", "test": "images/test",
                 "names": {i: c for i, c in enumerate(args.classes)}}
    (out / "data.yaml").write_text(yaml.safe_dump(data_yaml, sort_keys=False))

    print(f"\nimages: {n}  (train {len(splits['train'])}, val {len(splits['val'])}, test {len(splits['test'])})")
    print("boxes per class:", dict(box_counts))
    print("other:", dict(stats))
    print(f"data.yaml -> {out / 'data.yaml'}")
    return splits, box_counts, stats


if __name__ == "__main__":
    main()
