from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

from jobpilot_api.domain.copilot import CopilotInput, CopilotKind, CopilotSource


def test_copilot_dataset_contains_twenty_unique_synthetic_cross_feature_samples() -> None:
    dataset_path = (
        Path(__file__).resolve().parents[4] / "docs" / "evaluation" / "copilot" / "dataset-v1.json"
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    samples = dataset["samples"]

    assert dataset["provenance"] == "synthetic"
    assert dataset["containsPersonalData"] is False
    assert len(samples) == 20
    assert len({sample["id"] for sample in samples}) == 20
    assert {sample["kind"] for sample in samples} == {
        "MATCH",
        "RESUME_ADVICE",
        "INTERVIEW_PREP",
    }
    assert {sample["sourceStyle"] for sample in samples} == {"boss", "nowcoder"}
    assert sum(sample["sourceStyle"] == "boss" for sample in samples) == 10
    for sample in samples:
        serialized = json.dumps(sample, ensure_ascii=False)
        assert "@" not in serialized
        assert "http://" not in serialized
        assert "https://" not in serialized
        assert sample["jobSources"]
        if sample["kind"] in {"MATCH", "RESUME_ADVICE"}:
            assert sample["resume"]


def test_copilot_evaluator_blocks_an_incomplete_dataset_before_provider_access(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "run.json"
    dataset_path.write_text(
        json.dumps(
            {
                "datasetVersion": 1,
                "provenance": "synthetic",
                "containsPersonalData": False,
                "samples": [{"id": f"copilot-{index:03d}"} for index in range(1, 20)],
            }
        ),
        encoding="utf-8",
    )
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"

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
    assert "exactly 20 synthetic samples" in result.stderr
    assert not output_path.exists()


def test_copilot_evaluator_counts_grounding_and_unsafe_language_without_raw_output() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    copilot_input = CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="数据产品经理",
        job_sources=(CopilotSource("job-1", "能够使用 SQL 分析业务数据"),),
        resume_source=CopilotSource("resume-1", "使用 Excel 整理业务周报"),
    )
    raw_content = json.dumps(
        {
            "gaps": [
                {
                    "text": "用户不会 SQL",
                    "sourceEvidence": {
                        "text": "不存在的岗位原文",
                        "sourceType": "JOB",
                        "sourceId": "job-1",
                    },
                }
            ],
            "possibleQuestions": [
                {
                    "question": "面试官一定会问 Excel",
                    "sourceEvidence": {
                        "text": "使用 Excel 整理业务周报",
                        "sourceType": "RESUME",
                        "sourceId": "resume-1",
                    },
                }
            ],
        },
        ensure_ascii=False,
    )

    assert functions["_evidence_counts"](raw_content, copilot_input) == (2, 1)
    assert functions["_unsafe_language_counts"](raw_content) == (1, 1)


def test_unsafe_language_counts_tolerates_non_array_provider_fields() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))

    raw_content = json.dumps(
        {"gaps": {"text": "用户不会 SQL"}, "possibleQuestions": 42},
        ensure_ascii=False,
    )

    assert functions["_unsafe_language_counts"](raw_content) == (0, 0)
