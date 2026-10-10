import cv2
import numpy as np
import yaml

from model.prepare_dataset import check_label_lines, main


def test_label_checks():
    assert check_label_lines(["0 0.5 0.5 0.2 0.2"], 2) == []
    assert check_label_lines(["3 0.5 0.5 0.2 0.2"], 2)
    assert check_label_lines(["0 1.5 0.5 0.2 0.2"], 2)
    assert check_label_lines(["0 0.5 0.5"], 2)


def test_merge_remap_dedupe_split(tmp_path):
    src = tmp_path / "roboflow"
    (src / "train" / "images").mkdir(parents=True)
    (src / "train" / "labels").mkdir(parents=True)
    (src / "data.yaml").write_text(yaml.safe_dump({"names": ["Smoke", "Fire"]}))
    for i in range(10):
        img = np.full((20, 20, 3), i * 20, np.uint8)
        cv2.imwrite(str(src / "train" / "images" / f"{i}.jpg"), img)
        (src / "train" / "labels" / f"{i}.txt").write_text("1 0.5 0.5 0.2 0.2\n0 0.3 0.3 0.1 0.1\n" if i < 8 else "")
    cv2.imwrite(str(src / "train" / "images" / "dup.jpg"), np.full((20, 20, 3), 0, np.uint8))

    out = tmp_path / "out"
    splits, boxes, stats = main(["--inputs", str(src), "--out", str(out), "--class-map", "Fire=fire", "Smoke=smoke"])
    assert sum(len(v) for v in splits.values()) == 10 and stats["duplicates_skipped"] == 1
    assert boxes == {"fire": 8, "smoke": 8}
    data = yaml.safe_load((out / "data.yaml").read_text())
    assert data["names"] == {0: "fire", 1: "smoke"}
    first = next((out / "labels" / "train").glob("*.txt")).read_text().split("\n")[0]
    assert first == "" or first.split()[0] in {"0", "1"}


def test_group_split_keeps_video_frames_and_augmented_copies_together():
    from pathlib import Path

    from model.prepare_dataset import source_group, split_items

    assert source_group(Path("fire2_mp4-17_jpg.rf.abc.jpg")) == source_group(Path("fire2_mp4-3_jpg.rf.def.jpg"))
    assert source_group(Path("img_12_jpg.rf.a.jpg")) == source_group(Path("img_12_jpg.rf.b.jpg"))
    assert source_group(Path("img_12_jpg.rf.a.jpg")) != source_group(Path("img_13_jpg.rf.a.jpg"))
    assert source_group(Path("candle_lab_1791609151968.jpg")) == source_group(Path("candle_lab_1791609152968.jpg"))

    items = [(Path(f"v{g}_mp4-{i}.jpg"), [], f"v{g}") for g in range(20) for i in range(5)]
    items += [(Path(f"img_{i}.jpg"), [], f"img{i}") for i in range(100)]
    splits = split_items(items, [0.7, 0.2, 0.1], seed=1)
    assert sum(len(v) for v in splits.values()) == 200
    seen = {}
    for name, rows in splits.items():
        for _, _, g in rows:
            assert seen.setdefault(g, name) == name   # a group never spans two splits
    assert 30 <= len(splits["val"]) <= 50 and 15 <= len(splits["test"]) <= 25
