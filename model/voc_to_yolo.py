"""Convert Pascal-VOC XML annotations (LabelImg, FireNET, many Kaggle sets) to YOLO .txt labels.

    python -m model.voc_to_yolo --images data/firenet/train/images --annotations data/firenet/train/annotations \
        --out data/firenet_yolo --classes fire smoke

Writes <out>/images/*.jpg and <out>/labels/*.txt plus a classes.txt, ready for prepare_dataset.py.
"""
from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def convert_xml(xml_text: str, classes: list[str], class_map: dict[str, str] | None = None) -> list[str]:
    """Return YOLO label lines for one VOC annotation."""
    root = ET.fromstring(xml_text)
    w = float(root.findtext("size/width"))
    h = float(root.findtext("size/height"))
    lines = []
    for obj in root.iter("object"):
        name = (obj.findtext("name") or "").strip()
        name = (class_map or {}).get(name, name).lower()
        if name not in classes:
            continue
        box = obj.find("bndbox")
        x1, y1, x2, y2 = (float(box.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, x2 = max(0.0, min(x1, x2)), min(w, max(x1, x2))
        y1, y2 = max(0.0, min(y1, y2)), min(h, max(y1, y2))
        if x2 - x1 < 1 or y2 - y1 < 1:
            continue
        lines.append(f"{classes.index(name)} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                     f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return lines


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--images", required=True)
    p.add_argument("--annotations", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--classes", nargs="+", default=["fire", "smoke"])
    p.add_argument("--class-map", nargs="*", default=[], help='e.g. "flame=fire"')
    p.add_argument("--prefix", default="", help="prefix added to output file names (avoids clashes when merging)")
    args = p.parse_args(argv)

    class_map = dict(item.split("=", 1) for item in args.class_map)
    out_img, out_lab = Path(args.out) / "images", Path(args.out) / "labels"
    out_img.mkdir(parents=True, exist_ok=True)
    out_lab.mkdir(parents=True, exist_ok=True)
    images = {f.stem: f for f in Path(args.images).iterdir() if f.suffix.lower() in IMG_EXT}
    n_img = n_box = 0
    for xml in sorted(Path(args.annotations).glob("*.xml")):
        img = images.get(xml.stem)
        if img is None:
            continue
        lines = convert_xml(xml.read_text(encoding="utf-8", errors="ignore"), args.classes, class_map)
        stem = (args.prefix + img.stem).replace(" ", "_").replace("(", "").replace(")", "")
        shutil.copy2(img, out_img / f"{stem}{img.suffix.lower()}")
        (out_lab / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        n_img, n_box = n_img + 1, n_box + len(lines)
    (Path(args.out) / "classes.txt").write_text("\n".join(args.classes) + "\n")
    print(f"converted {n_img} images, {n_box} boxes -> {args.out}")


if __name__ == "__main__":
    main()
