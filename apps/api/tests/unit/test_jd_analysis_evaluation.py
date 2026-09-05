from __future__ import annotations

import json
import subprocess
import sys
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

    assert dataset["goldReviewStatus"] == "human-reviewed"
    assert dataset["reviewedSampleCount"] == len(samples)
    assert len(samples) == 20
    assert len({sample["id"] for sample in samples}) == 20
    assert {sample["sourceStyle"] for sample in samples} == {"boss", "nowcoder"}
    assert sum(sample["sourceStyle"] == "boss" for sample in samples) == 10
    for sample in samples:
        assert sample["goldReviewStatus"] == "human-reviewed"
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


def test_evaluator_blocks_incomplete_per_sample_human_review(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "run.json"
    dataset_path.write_text(
        json.dumps(
            {
                "datasetVersion": 1,
                "goldReviewStatus": "human-reviewed",
                "reviewedSampleCount": 20,
                "samples": [{"id": f"jd-{index:03d}"} for index in range(1, 21)],
            }
        ),
        encoding="utf-8",
    )
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_jd_analysis.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dataset",
            str(dataset_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert "human review is incomplete" in result.stderr
    assert not output_path.exists()
