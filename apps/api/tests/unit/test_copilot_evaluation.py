from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

from jobpilot_api.application.providers import CopilotRepairRequest
from jobpilot_api.domain.copilot import CopilotInput, CopilotKind, CopilotSource
from jobpilot_api.domain.errors import AnalysisTimeoutError


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


def test_copilot_evaluator_counts_all_sources_when_source_ids_repeat() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    copilot_input = CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="AI 产品经理",
        job_sources=(
            CopilotSource("job-1", "负责大模型产品的需求分析与版本规划"),
            CopilotSource("job-1", "能够使用 SQL 分析业务数据"),
        ),
        resume_source=CopilotSource(
            "resume-1", "在智能问答项目中负责用户调研、需求文档和版本验收。"
        ),
    )
    raw_content = json.dumps(
        {
            "strengths": [
                {
                    "text": "有智能问答项目经验",
                    "sourceEvidence": {
                        "text": "负责用户调研、需求文档和版本验收",
                        "sourceType": "RESUME",
                        "sourceId": "resume-1",
                    },
                }
            ],
            "gaps": [
                {
                    "text": "当前简历未发现大模型产品规划经验",
                    "sourceEvidence": {
                        "text": "负责大模型产品的需求分析与版本规划",
                        "sourceType": "JOB",
                        "sourceId": "job-1",
                    },
                },
                {
                    "text": "当前简历未发现 SQL 分析经验",
                    "sourceEvidence": {
                        "text": "能够使用 SQL 分析业务数据",
                        "sourceType": "JOB",
                        "sourceId": "job-1",
                    },
                },
            ],
        },
        ensure_ascii=False,
    )

    assert functions["_evidence_counts"](raw_content, copilot_input) == (3, 3)


def test_v2_evaluator_records_first_pass_and_one_successful_repair_without_raw_output() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    invalid_marker = "PRIVATE_INVALID_PROVIDER_RESPONSE"
    valid = json.dumps(
        {
            "summary": "匹配结论",
            "strengths": [
                {
                    "text": "具备需求分析经历",
                    "sourceEvidence": {
                        "text": "负责用户调研",
                        "sourceType": "RESUME",
                        "sourceId": "resume-1",
                    },
                }
            ],
            "gaps": [],
            "suggestions": ["准备需求分析案例"],
        },
        ensure_ascii=False,
    )

    class Provider:
        model = "fictional-model"

        def __init__(self) -> None:
            self.calls: list[CopilotRepairRequest | None] = []
            self.responses = [invalid_marker, valid]

        def generate_copilot(
            self,
            _copilot_input: CopilotInput,
            *,
            system_instruction: str,
            repair: CopilotRepairRequest | None = None,
        ) -> str:
            assert "ALLOWED_SOURCE_IDS_JSON" in system_instruction
            self.calls.append(repair)
            return self.responses.pop(0)

    provider = Provider()
    entry = functions["_evaluate_sample"](
        {
            "id": "copilot-test",
            "kind": "MATCH",
            "title": "产品经理",
            "jobSources": [{"id": "job-1", "text": "负责需求分析"}],
            "resume": {"id": "resume-1", "text": "负责用户调研"},
            "interviews": [],
        },
        provider,
    )

    assert entry["firstPassSchemaValid"] is False
    assert entry["finalSchemaValid"] is True
    assert entry["retryCount"] == 1
    assert entry["attemptCount"] == 2
    assert entry["evidence"] == {"grounded": 1, "provided": 1}
    assert provider.calls[0] is None
    assert provider.calls[1] is not None
    assert provider.calls[1].validator_error == "INVALID_JSON"
    assert invalid_marker not in json.dumps(entry, ensure_ascii=False)


def test_v2_evaluator_stops_after_one_failed_repair_and_keeps_only_sanitized_error() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    private_markers = ["PRIVATE_FIRST_RESPONSE", "PRIVATE_SECOND_RESPONSE"]

    class Provider:
        model = "fictional-model"

        def __init__(self) -> None:
            self.repairs: list[CopilotRepairRequest | None] = []

        def generate_copilot(
            self,
            _copilot_input: CopilotInput,
            *,
            system_instruction: str,
            repair: CopilotRepairRequest | None = None,
        ) -> str:
            self.repairs.append(repair)
            return private_markers[len(self.repairs) - 1]

    provider = Provider()
    entry = functions["_evaluate_sample"](
        {
            "id": "copilot-test",
            "kind": "MATCH",
            "title": "产品经理",
            "jobSources": [{"id": "job-1", "text": "负责需求分析"}],
            "resume": {"id": "resume-1", "text": "负责用户调研"},
            "interviews": [],
        },
        provider,
    )

    assert entry["firstPassSchemaValid"] is False
    assert entry["finalSchemaValid"] is False
    assert entry["retryCount"] == 1
    assert entry["attemptCount"] == 2
    assert entry["errorCode"] == "AI_INVALID_RESPONSE"
    assert len(provider.repairs) == 2
    serialized = json.dumps(entry, ensure_ascii=False)
    assert all(marker not in serialized for marker in private_markers)


def test_evaluator_records_timeout_retry_then_success_without_raw_error() -> None:
    functions = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py")
    )
    sample = {
        "id": "copilot-test",
        "kind": "MATCH",
        "title": "产品经理",
        "jobSources": [{"id": "job-1", "text": "负责需求分析"}],
        "resume": {"id": "resume-1", "text": "负责用户调研"},
        "interviews": [],
    }
    valid = json.dumps(
        {"summary": "匹配结论", "strengths": [], "gaps": [], "suggestions": []},
        ensure_ascii=False,
    )

    class Provider:
        def __init__(self) -> None:
            self.calls: list[CopilotRepairRequest | None] = []

        def generate_copilot(
            self,
            _copilot_input: CopilotInput,
            *,
            system_instruction: str,
            repair: CopilotRepairRequest | None = None,
        ) -> str:
            assert "ALLOWED_SOURCE_IDS_JSON" in system_instruction
            self.calls.append(repair)
            if len(self.calls) == 1:
                raise AnalysisTimeoutError("PRIVATE_TIMEOUT_DETAIL")
            return valid

    provider = Provider()
    entry = functions["_evaluate_sample"](sample, provider)

    assert entry["firstAttemptResult"] == "AI_TIMEOUT"
    assert entry["firstAttemptLatencyMs"] >= 0
    assert entry["timeoutRetryTriggered"] is True
    assert entry["retryResult"] == "PASS"
    assert entry["retryLatencyMs"] >= 0
    assert entry["totalLatencyMs"] >= entry["firstAttemptLatencyMs"]
    assert entry["attemptCount"] == entry["retryCount"] + 1 == 2
    assert entry["finalSchemaValid"] is True
    assert provider.calls == [None, None]
    assert "PRIVATE_TIMEOUT_DETAIL" not in json.dumps(entry, ensure_ascii=False)
    metrics = functions["_aggregate_metrics"]([entry])
    assert metrics["retryUsage"]["samplesRetried"] == 1
    assert metrics["timeoutRetryUsage"]["samplesRetried"] == 1
    assert metrics["repairUsage"]["samplesRetried"] == 0


def test_evaluator_records_second_timeout_without_third_call() -> None:
    functions = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py")
    )
    sample = {
        "id": "copilot-test",
        "kind": "MATCH",
        "title": "产品经理",
        "jobSources": [{"id": "job-1", "text": "负责需求分析"}],
        "resume": {"id": "resume-1", "text": "负责用户调研"},
        "interviews": [],
    }

    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_copilot(
            self,
            _copilot_input: CopilotInput,
            *,
            system_instruction: str,
            repair: CopilotRepairRequest | None = None,
        ) -> str:
            self.calls += 1
            assert repair is None
            raise AnalysisTimeoutError("PRIVATE_TIMEOUT_DETAIL")

    provider = Provider()
    entry = functions["_evaluate_sample"](sample, provider)

    assert entry["firstAttemptResult"] == "AI_TIMEOUT"
    assert entry["timeoutRetryTriggered"] is True
    assert entry["retryResult"] == "AI_TIMEOUT"
    assert entry["retryLatencyMs"] >= 0
    assert entry["errorCode"] == "AI_TIMEOUT"
    assert entry["finalSchemaValid"] is False
    assert entry["attemptCount"] == 2
    assert provider.calls == 2
    assert "PRIVATE_TIMEOUT_DETAIL" not in json.dumps(entry, ensure_ascii=False)


def test_evaluator_does_not_repair_invalid_content_after_timeout_retry() -> None:
    functions = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py")
    )
    sample = {
        "id": "copilot-test",
        "kind": "MATCH",
        "title": "产品经理",
        "jobSources": [{"id": "job-1", "text": "负责需求分析"}],
        "resume": {"id": "resume-1", "text": "负责用户调研"},
        "interviews": [],
    }

    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def generate_copilot(
            self,
            _copilot_input: CopilotInput,
            *,
            system_instruction: str,
            repair: CopilotRepairRequest | None = None,
        ) -> str:
            self.calls += 1
            assert repair is None
            if self.calls == 1:
                raise AnalysisTimeoutError("PRIVATE_TIMEOUT_DETAIL")
            return '{"summary":"incomplete"}'

    provider = Provider()
    entry = functions["_evaluate_sample"](sample, provider)

    assert entry["firstAttemptResult"] == "AI_TIMEOUT"
    assert entry["retryResult"] == "AI_INVALID_RESPONSE"
    assert entry["errorCode"] == "AI_INVALID_RESPONSE"
    assert entry["attemptCount"] == 2
    assert provider.calls == 2
    assert "PRIVATE_TIMEOUT_DETAIL" not in json.dumps(entry, ensure_ascii=False)


def test_v2_preflight_selects_one_sample_per_kind_and_requires_every_gate() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    samples = [
        {"id": "copilot-001", "kind": "MATCH"},
        {"id": "copilot-009", "kind": "RESUME_ADVICE"},
        {"id": "copilot-017", "kind": "INTERVIEW_PREP"},
        {"id": "copilot-020", "kind": "INTERVIEW_PREP"},
    ]
    selected = functions["_preflight_samples"](samples)
    passing_entries = [
        {
            "finalSchemaValid": True,
            "evidence": {"grounded": 2, "provided": 2},
            "gapLanguageViolations": 0,
            "interviewCertaintyViolations": 0,
            "suggestionSafetyViolations": 0,
            "interviewCategoryRelevanceViolations": 0,
        }
        for _sample in selected
    ]

    assert [sample["id"] for sample in selected] == [
        "copilot-001",
        "copilot-009",
        "copilot-017",
    ]
    assert functions["_preflight_passes"](passing_entries) is True
    passing_entries[2]["interviewCategoryRelevanceViolations"] = 1
    assert functions["_preflight_passes"](passing_entries) is False


def test_unsafe_language_counts_tolerates_non_array_provider_fields() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))

    raw_content = json.dumps(
        {"gaps": {"text": "用户不会 SQL"}, "possibleQuestions": 42},
        ensure_ascii=False,
    )

    assert functions["_unsafe_language_counts"](raw_content) == (0, 0)


def test_copilot_failure_diagnostic_classifies_non_json_fence_and_truncation() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    diagnose = functions["_failure_diagnostic"]
    copilot_input = CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="产品经理",
        job_sources=(CopilotSource("job-1", "负责需求分析"),),
        resume_source=CopilotSource("resume-1", "负责用户调研"),
    )

    assert diagnose("not json", CopilotKind.MATCH, copilot_input)["failureType"] == "A_NON_JSON"
    assert (
        diagnose("```json\n{}\n```", CopilotKind.MATCH, copilot_input)["failureType"]
        == "B_MARKDOWN_CODE_FENCE"
    )
    assert (
        diagnose('{"summary":"ok","strengths":[', CopilotKind.MATCH, copilot_input)["failureType"]
        == "G_TRUNCATED_OUTPUT"
    )


def test_copilot_failure_diagnostic_classifies_schema_and_evidence_failures() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    diagnose = functions["_failure_diagnostic"]
    copilot_input = CopilotInput.create(
        kind=CopilotKind.INTERVIEW_PREP,
        title="产品经理",
        job_sources=(CopilotSource("job-1", "负责需求分析"),),
    )

    missing = json.dumps({"possibleQuestions": []}, ensure_ascii=False)
    wrong_type = json.dumps(
        {
            "possibleQuestions": "none",
            "review": {"strengths": [], "weaknesses": [], "nextActions": []},
        },
        ensure_ascii=False,
    )
    invalid_enum = json.dumps(
        {
            "possibleQuestions": [
                {
                    "category": "SALES",
                    "question": "如何分析需求？",
                    "reason": "岗位要求",
                    "sourceEvidence": {
                        "text": "负责需求分析",
                        "sourceType": "JOB",
                        "sourceId": "job-1",
                    },
                }
            ],
            "review": {"strengths": [], "weaknesses": [], "nextActions": []},
        },
        ensure_ascii=False,
    )
    unsupported_evidence = invalid_enum.replace('"SALES"', '"PRODUCT"').replace(
        '"负责需求分析"', '"不存在的要求"'
    )

    assert (
        diagnose(missing, CopilotKind.INTERVIEW_PREP, copilot_input)["failureType"]
        == "C_MISSING_FIELD"
    )
    assert (
        diagnose(wrong_type, CopilotKind.INTERVIEW_PREP, copilot_input)["failureType"]
        == "D_WRONG_TYPE"
    )
    assert (
        diagnose(invalid_enum, CopilotKind.INTERVIEW_PREP, copilot_input)["failureType"]
        == "E_INVALID_ENUM"
    )
    evidence_result = diagnose(unsupported_evidence, CopilotKind.INTERVIEW_PREP, copilot_input)
    assert evidence_result["failureType"] == "F_EVIDENCE_STRUCTURE"
    assert "不存在的要求" not in json.dumps(evidence_result, ensure_ascii=False)


def test_copilot_failure_diagnostic_records_only_sanitized_shape() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    secret_marker = "DO_NOT_PERSIST_PROVIDER_CONTENT"
    result = functions["_failure_diagnostic"](
        json.dumps(
            {
                "highlight": [],
                "possibleImprovement": secret_marker,
                "interviewFocus": [],
            }
        ),
        CopilotKind.RESUME_ADVICE,
        CopilotInput.create(
            kind=CopilotKind.RESUME_ADVICE,
            title="产品经理",
            job_sources=(CopilotSource("job-1", "负责需求分析"),),
            resume_source=CopilotSource("resume-1", "负责用户调研"),
        ),
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["failureType"] == "D_WRONG_TYPE"
    assert (
        result["actualShape"]
        == "object{highlight:list,interviewFocus:list,possibleImprovement:string}"
    )
    assert secret_marker not in serialized

    malicious_key = functions["_failure_diagnostic"](
        json.dumps(
            {
                "highlight": [],
                "possibleImprovement": [],
                "interviewFocus": [],
                secret_marker: "ignored",
            }
        ),
        CopilotKind.RESUME_ADVICE,
        CopilotInput.create(
            kind=CopilotKind.RESUME_ADVICE,
            title="产品经理",
            job_sources=(CopilotSource("job-1", "负责需求分析"),),
            resume_source=CopilotSource("resume-1", "负责用户调研"),
        ),
    )

    malicious_serialized = json.dumps(malicious_key, ensure_ascii=False)
    assert malicious_key["failureType"] == "H_OTHER"
    assert "unknownFields:1" in malicious_key["actualShape"]
    assert secret_marker not in malicious_serialized


def test_copilot_failure_diagnostic_selects_only_baseline_bad_cases() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    dataset_samples = [
        {"id": "copilot-001"},
        {"id": "copilot-002"},
        {"id": "copilot-003"},
    ]
    baseline = {
        "runType": "REAL_PROVIDER_OUTPUT_ONLY",
        "datasetVersion": 1,
        "promptVersions": {
            "MATCH": "match-v1",
            "RESUME_ADVICE": "resume-advice-v1",
            "INTERVIEW_PREP": "interview-prep-v1",
        },
        "badCases": [
            {"id": "copilot-002", "reason": "AI_INVALID_RESPONSE"},
            {"id": "copilot-003", "reason": "AI_TIMEOUT"},
        ],
    }

    assert functions["_diagnostic_sample_ids"](baseline, 1, dataset_samples) == ("copilot-002",)


def test_copilot_failure_diagnostic_rejects_non_v1_or_unknown_baseline_samples() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    dataset_samples = [{"id": "copilot-001"}]
    invalid_baseline = {
        "runType": "REAL_PROVIDER_OUTPUT_ONLY",
        "datasetVersion": 1,
        "promptVersions": {"MATCH": "match-v2"},
        "badCases": [{"id": "copilot-999", "reason": "AI_INVALID_RESPONSE"}],
    }

    try:
        functions["_diagnostic_sample_ids"](invalid_baseline, 1, dataset_samples)
    except ValueError as error:
        assert str(error) == "diagnostic source must be the frozen V1 run"
    else:
        raise AssertionError("invalid V1 diagnostic source must be rejected")


def test_copilot_failure_diagnostic_keeps_v1_interview_category_contract() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_copilot.py"
    functions = runpy.run_path(str(script_path))
    copilot_input = CopilotInput.create(
        kind=CopilotKind.INTERVIEW_PREP,
        title="AI 产品经理",
        job_sources=(CopilotSource("job-1", "负责 AI 产品需求分析"),),
    )
    questions = [
        {
            "category": category,
            "question": f"可能关注方向：{category} 场景。",
            "reason": "岗位要求 AI 产品需求分析。",
            "sourceEvidence": {
                "text": "负责 AI 产品需求分析",
                "sourceType": "JOB",
                "sourceId": "job-1",
            },
        }
        for category in ("PRODUCT", "AI", "PROJECT")
    ]
    raw_content = json.dumps(
        {
            "possibleQuestions": questions,
            "review": {"strengths": [], "weaknesses": [], "nextActions": []},
        },
        ensure_ascii=False,
    )

    assert (
        functions["_failure_diagnostic"](raw_content, CopilotKind.INTERVIEW_PREP, copilot_input)[
            "failureType"
        ]
        == "NO_FAILURE_REPRODUCED"
    )
