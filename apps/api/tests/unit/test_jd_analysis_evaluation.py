from __future__ import annotations

import json
from pathlib import Path


def test_evaluation_dataset_has_unique_deidentified_samples_and_review_is_honest() -> None:
    dataset_path = (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "evaluation"
        / "jd-analysis"
        / "dataset-v1.json"
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    samples = dataset["samples"]

    assert dataset["goldReviewStatus"] == "pending-human-review"
    assert len(samples) == 20
    assert len({sample["id"] for sample in samples}) == 20
    assert {sample["sourceStyle"] for sample in samples} == {"boss", "nowcoder"}
    assert sum(sample["sourceStyle"] == "boss" for sample in samples) == 10
    for sample in samples:
        assert "@" not in sample["description"]
        assert "http://" not in sample["description"]
        assert "https://" not in sample["description"]
        assert set(sample["gold"]) == {
            "responsibilities",
            "mustHaveRequirements",
            "preferredRequirements",
            "skills",
            "experienceRequirements",
            "educationRequirements",
        }
