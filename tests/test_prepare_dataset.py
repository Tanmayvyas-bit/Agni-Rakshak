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
