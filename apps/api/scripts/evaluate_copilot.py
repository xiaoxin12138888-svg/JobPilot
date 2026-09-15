from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobpilot_api.application.copilot import (  # noqa: E402
    INTERVIEW_PREP_PROMPT_V1,
    MATCH_PROMPT_V1,
    PROMPTS,
    RESUME_ADVICE_PROMPT_V1,
)
from jobpilot_api.config import ApiSettings  # noqa: E402
from jobpilot_api.domain.copilot import (  # noqa: E402
    CopilotInput,
    CopilotKind,
    CopilotSource,
    InterviewQuestionCategory,
    SourceType,
    parse_copilot_result,
)
from jobpilot_api.domain.errors import DomainError  # noqa: E402
from jobpilot_api.infrastructure.ai.openai_compatible import (  # noqa: E402
    OpenAICompatibleJDAnalysisProvider,
)

INABILITY = re.compile(r"用户(?:不会|没有|不具备|无法)|候选人(?:不会|没有|不具备|无法)")
CERTAINTY = re.compile(r"一定会问|肯定会问|必问|面试官会问")
EXPECTED_SCHEMAS = {
    CopilotKind.MATCH: (
        "object{summary:string,strengths:GroundedItem[],gaps:GroundedItem[],suggestions:string[]}"
    ),
    CopilotKind.RESUME_ADVICE: (
        "object{highlight:GroundedItem[],possibleImprovement:string[],"
        "interviewFocus:GroundedItem[]}"
    ),
    CopilotKind.INTERVIEW_PREP: (
        "object{possibleQuestions:Question[],review:{strengths:GroundedItem[],"
        "weaknesses:GroundedItem[],nextActions:string[]}}"
    ),
}
V1_PROMPTS = {
    CopilotKind.MATCH: ("match-v1", MATCH_PROMPT_V1),
    CopilotKind.RESUME_ADVICE: ("resume-advice-v1", RESUME_ADVICE_PROMPT_V1),
    CopilotKind.INTERVIEW_PREP: ("interview-prep-v1", INTERVIEW_PREP_PROMPT_V1),
}
KNOWN_RESPONSE_FIELDS = {
    "category",
    "gaps",
    "highlight",
    "interviewFocus",
    "nextActions",
    "possibleImprovement",
    "possibleQuestions",
    "question",
    "reason",
    "review",
    "sourceEvidence",
    "sourceId",
    "sourceType",
    "strengths",
    "suggestions",
    "summary",
    "text",
    "weaknesses",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real AI Copilot evaluation")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--diagnose-failures-from",
        type=Path,
        help="Replay only AI_INVALID_RESPONSE samples from a frozen V1 run",
    )
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    samples = dataset.get("samples")
    if not _is_complete_synthetic_dataset(dataset, samples):
        print(
            "BLOCKED: evaluation dataset must contain exactly 20 synthetic samples", file=sys.stderr
        )
        return 2

    settings = ApiSettings.from_environment().llm
    if settings is None:
        print("BLOCKED: Provider configuration is incomplete or invalid", file=sys.stderr)
        return 2

    provider = OpenAICompatibleJDAnalysisProvider(settings)
    if args.diagnose_failures_from is not None:
        try:
            baseline_path = args.diagnose_failures_from.resolve()
            if args.output.resolve() == baseline_path:
                raise ValueError("diagnostic output must not overwrite the V1 baseline")
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            sample_ids = _diagnostic_sample_ids(
                baseline,
                dataset["datasetVersion"],
                samples,
            )
        except (json.JSONDecodeError, OSError, ValueError) as error:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 2
        return _run_failure_diagnostics(
            samples,
            sample_ids,
            provider,
            settings.model,
            settings.timeout_seconds,
            dataset["datasetVersion"],
            args.output,
        )

    entries: list[dict[str, Any]] = []
    bad_cases: list[dict[str, str]] = []
    evidence_provided = 0
    evidence_grounded = 0
    gap_language_violations = 0
    certainty_violations = 0
    schema_valid = 0

    for sample in samples:
        kind = CopilotKind(sample["kind"])
        copilot_input = _input_from_sample(sample, kind)
        entry: dict[str, Any] = {
            "id": sample["id"],
            "kind": kind.value,
            "schemaValid": False,
        }
        started_at = time.perf_counter()
        try:
            raw_content = provider.generate_copilot(
                copilot_input,
                system_instruction=PROMPTS[kind][1],
            )
            provided, grounded = _evidence_counts(raw_content, copilot_input)
            evidence_provided += provided
            evidence_grounded += grounded
            gaps, questions = _unsafe_language_counts(raw_content)
            gap_language_violations += gaps
            certainty_violations += questions
            result = parse_copilot_result(kind, raw_content, copilot_input)
            entry["schemaValid"] = True
            entry["result"] = result.as_dict()
            schema_valid += 1
        except DomainError as error:
            entry["errorCode"] = error.code
            bad_cases.append(
                {
                    "id": sample["id"],
                    "kind": kind.value,
                    "reason": error.code,
                }
            )
        entry["latencyMs"] = round((time.perf_counter() - started_at) * 1000)
        print(
            f"{entry['id']}: {'PASS' if entry['schemaValid'] else 'FAIL'} "
            f"({entry['latencyMs']} ms)",
            flush=True,
        )
        entries.append(entry)

    output = {
        "datasetVersion": dataset["datasetVersion"],
        "runType": "REAL_PROVIDER_OUTPUT_ONLY",
        "promptVersions": {
            kind.value: PROMPTS[kind][0]
            for kind in (
                CopilotKind.MATCH,
                CopilotKind.RESUME_ADVICE,
                CopilotKind.INTERVIEW_PREP,
            )
        },
        "schemaVersion": 1,
        "model": settings.model,
        "temperature": 0,
        "timeoutSeconds": settings.timeout_seconds,
        "sampleCount": len(samples),
        "metrics": {
            "schemaSuccess": {"valid": schema_valid, "total": len(samples)},
            "evidenceGrounding": {
                "grounded": evidence_grounded,
                "provided": evidence_provided,
            },
            "unsupportedHallucinationCount": evidence_provided - evidence_grounded,
            "gapLanguageViolations": gap_language_violations,
            "interviewCertaintyViolations": certainty_violations,
        },
        "humanContentReview": {
            "status": "NOT_RUN",
            "dimensions": ["summary usefulness", "suggestion usefulness", "question relevance"],
        },
        "badCases": bad_cases,
        "samples": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def _run_failure_diagnostics(
    samples: list[dict[str, Any]],
    sample_ids: tuple[str, ...],
    provider: OpenAICompatibleJDAnalysisProvider,
    model: str,
    timeout_seconds: float,
    dataset_version: int,
    output_path: Path,
) -> int:
    selected = {sample["id"]: sample for sample in samples if sample["id"] in sample_ids}
    entries: list[dict[str, Any]] = []
    for sample_id in sample_ids:
        sample = selected[sample_id]
        kind = CopilotKind(sample["kind"])
        copilot_input = _input_from_sample(sample, kind)
        started_at = time.perf_counter()
        try:
            raw_content = provider.generate_copilot(
                copilot_input,
                system_instruction=V1_PROMPTS[kind][1],
            )
            diagnostic = _failure_diagnostic(raw_content, kind, copilot_input)
        except DomainError as error:
            diagnostic = {
                "expectedSchema": EXPECTED_SCHEMAS[kind],
                "failureType": "H_OTHER",
                "actualShape": "not-received",
                "validationIssue": f"Provider call failed with sanitized code {error.code}",
            }
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        entry = {
            "id": sample_id,
            "kind": kind.value,
            **diagnostic,
            "latencyMs": latency_ms,
        }
        entries.append(entry)
        print(f"{sample_id}: {diagnostic['failureType']} ({latency_ms} ms)", flush=True)

    output = {
        "datasetVersion": dataset_version,
        "runType": "V1_FAILURE_DIAGNOSTIC",
        "promptVersions": {kind.value: V1_PROMPTS[kind][0] for kind in CopilotKind},
        "model": model,
        "temperature": 0,
        "timeoutSeconds": timeout_seconds,
        "sampleCount": len(entries),
        "rawProviderOutputPersisted": False,
        "samples": entries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def _diagnostic_sample_ids(
    baseline: dict[str, Any],
    dataset_version: int,
    samples: list[dict[str, Any]],
) -> tuple[str, ...]:
    expected_versions = {kind.value: V1_PROMPTS[kind][0] for kind in CopilotKind}
    if (
        baseline.get("runType") != "REAL_PROVIDER_OUTPUT_ONLY"
        or baseline.get("datasetVersion") != dataset_version
        or baseline.get("promptVersions") != expected_versions
    ):
        raise ValueError("diagnostic source must be the frozen V1 run")
    known_ids = {sample.get("id") for sample in samples}
    bad_cases = baseline.get("badCases")
    if not isinstance(bad_cases, list):
        raise ValueError("diagnostic source has no V1 bad cases")
    ids = tuple(
        item.get("id")
        for item in bad_cases
        if isinstance(item, dict) and item.get("reason") == "AI_INVALID_RESPONSE"
    )
    if not ids or len(ids) != len(set(ids)) or any(sample_id not in known_ids for sample_id in ids):
        raise ValueError("diagnostic source contains invalid V1 failure sample IDs")
    return ids


def _is_complete_synthetic_dataset(dataset: dict[str, Any], samples: object) -> bool:
    if (
        dataset.get("provenance") != "synthetic"
        or dataset.get("containsPersonalData") is not False
        or not isinstance(samples, list)
        or len(samples) != 20
    ):
        return False
    try:
        ids = {sample["id"] for sample in samples}
        kinds = {CopilotKind(sample["kind"]) for sample in samples}
        for sample in samples:
            _input_from_sample(sample, CopilotKind(sample["kind"]))
    except (KeyError, TypeError, ValueError):
        return False
    return len(ids) == 20 and kinds == set(CopilotKind)


def _input_from_sample(sample: dict[str, Any], kind: CopilotKind) -> CopilotInput:
    resume = sample.get("resume")
    return CopilotInput.create(
        kind=kind,
        title=sample["title"],
        job_sources=tuple(
            CopilotSource(source["id"], source["text"]) for source in sample["jobSources"]
        ),
        resume_source=(CopilotSource(resume["id"], resume["text"]) if resume is not None else None),
        interview_sources=tuple(
            CopilotSource(source["id"], source["text"]) for source in sample.get("interviews", [])
        ),
    )


def _evidence_counts(raw_content: str, copilot_input: CopilotInput) -> tuple[int, int]:
    try:
        payload = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return 0, 0
    evidence = list(_source_evidence(payload))
    sources: dict[tuple[str, str], list[str]] = {}
    for source in copilot_input.job_sources:
        sources.setdefault(("JOB", source.id), []).append(source.text)
    if copilot_input.resume_source is not None:
        sources.setdefault(("RESUME", copilot_input.resume_source.id), []).append(
            copilot_input.resume_source.text
        )
    for source in copilot_input.interview_sources:
        sources.setdefault(("INTERVIEW", source.id), []).append(source.text)
    grounded = sum(
        bool(_key(item.get("text")))
        and any(
            _key(item.get("text", "")) in _key(source)
            for source in sources.get((item.get("sourceType"), item.get("sourceId")), [])
        )
        for item in evidence
        if isinstance(item, dict)
    )
    return len(evidence), grounded


def _source_evidence(value: object):
    if isinstance(value, dict):
        evidence = value.get("sourceEvidence")
        if isinstance(evidence, dict):
            yield evidence
        for item in value.values():
            yield from _source_evidence(item)
    elif isinstance(value, list):
        for item in value:
            yield from _source_evidence(item)


def _unsafe_language_counts(raw_content: str) -> tuple[int, int]:
    try:
        payload = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return 0, 0
    if not isinstance(payload, dict):
        return 0, 0
    gaps = payload.get("gaps", [])
    questions = payload.get("possibleQuestions", [])
    if not isinstance(gaps, list):
        gaps = []
    if not isinstance(questions, list):
        questions = []
    gap_violations = sum(
        isinstance(item, dict)
        and isinstance(item.get("text"), str)
        and ("未发现" not in item["text"] or INABILITY.search(item["text"]) is not None)
        for item in gaps
    )
    certainty_violations = sum(
        isinstance(item, dict)
        and isinstance(item.get("question"), str)
        and CERTAINTY.search(item["question"]) is not None
        for item in questions
    )
    return gap_violations, certainty_violations


def _failure_diagnostic(
    raw_content: str,
    kind: CopilotKind,
    copilot_input: CopilotInput,
) -> dict[str, str]:
    """Describe a Provider validation failure without retaining any response content."""
    stripped = raw_content.strip() if isinstance(raw_content, str) else ""
    base = {"expectedSchema": EXPECTED_SCHEMAS[kind]}
    if stripped.startswith("```"):
        return {
            **base,
            "failureType": "B_MARKDOWN_CODE_FENCE",
            "actualShape": "markdown-code-fence",
            "validationIssue": "response is wrapped in a Markdown code fence",
        }
    try:
        payload = json.loads(stripped)
    except (json.JSONDecodeError, TypeError) as error:
        truncated = bool(stripped) and (
            (stripped.startswith("{") and not stripped.endswith("}"))
            or (stripped.startswith("[") and not stripped.endswith("]"))
            or (isinstance(error, json.JSONDecodeError) and error.pos >= max(0, len(stripped) - 1))
        )
        return {
            **base,
            "failureType": "G_TRUNCATED_OUTPUT" if truncated else "A_NON_JSON",
            "actualShape": "truncated-json" if truncated else "non-json",
            "validationIssue": (
                "JSON output ended before the document was complete"
                if truncated
                else "response is not valid JSON"
            ),
        }

    actual_shape = _safe_shape(payload)
    if not isinstance(payload, dict):
        return {
            **base,
            "failureType": "D_WRONG_TYPE",
            "actualShape": actual_shape,
            "validationIssue": "top-level value must be an object",
        }
    problem = _schema_problem(kind, payload, copilot_input)
    if problem is not None:
        failure_type, issue = problem
        return {
            **base,
            "failureType": failure_type,
            "actualShape": actual_shape,
            "validationIssue": issue,
        }
    try:
        parse_copilot_result(kind, raw_content, copilot_input)
    except DomainError:
        return {
            **base,
            "failureType": "H_OTHER",
            "actualShape": actual_shape,
            "validationIssue": "strict parser rejected a semantic constraint",
        }
    return {
        **base,
        "failureType": "NO_FAILURE_REPRODUCED",
        "actualShape": actual_shape,
        "validationIssue": "response passed the frozen V1 parser on diagnostic replay",
    }


def _schema_problem(
    kind: CopilotKind,
    payload: dict[str, Any],
    copilot_input: CopilotInput,
) -> tuple[str, str] | None:
    expected_keys = {
        CopilotKind.MATCH: {"summary", "strengths", "gaps", "suggestions"},
        CopilotKind.RESUME_ADVICE: {"highlight", "possibleImprovement", "interviewFocus"},
        CopilotKind.INTERVIEW_PREP: {"possibleQuestions", "review"},
    }[kind]
    key_problem = _key_problem(payload, expected_keys, "top-level")
    if key_problem is not None:
        return key_problem

    if kind == CopilotKind.MATCH:
        if not isinstance(payload["summary"], str):
            return "D_WRONG_TYPE", "summary must be a string"
        for field, source_type in (("strengths", SourceType.RESUME), ("gaps", SourceType.JOB)):
            problem = _grounded_array_problem(field, payload[field], source_type, copilot_input)
            if problem is not None:
                return problem
        return _string_array_problem("suggestions", payload["suggestions"])

    if kind == CopilotKind.RESUME_ADVICE:
        for field, source_type in (
            ("highlight", SourceType.RESUME),
            ("interviewFocus", SourceType.JOB),
        ):
            problem = _grounded_array_problem(field, payload[field], source_type, copilot_input)
            if problem is not None:
                return problem
        return _string_array_problem("possibleImprovement", payload["possibleImprovement"])

    questions = payload["possibleQuestions"]
    if not isinstance(questions, list):
        return "D_WRONG_TYPE", "possibleQuestions must be an array"
    observed_categories: set[InterviewQuestionCategory] = set()
    for index, question in enumerate(questions):
        path = f"possibleQuestions[{index}]"
        if not isinstance(question, dict):
            return "D_WRONG_TYPE", f"{path} must be an object"
        problem = _key_problem(
            question,
            {"category", "question", "reason", "sourceEvidence"},
            path,
        )
        if problem is not None:
            return problem
        try:
            observed_categories.add(InterviewQuestionCategory(question["category"]))
        except (TypeError, ValueError):
            return "E_INVALID_ENUM", f"{path}.category is outside the V1 enum"
        for field in ("question", "reason"):
            if not isinstance(question[field], str):
                return "D_WRONG_TYPE", f"{path}.{field} must be a string"
        problem = _evidence_problem(
            f"{path}.sourceEvidence",
            question["sourceEvidence"],
            SourceType.JOB,
            copilot_input,
        )
        if problem is not None:
            return problem
    review = payload["review"]
    if not isinstance(review, dict):
        return "D_WRONG_TYPE", "review must be an object"
    problem = _key_problem(review, {"strengths", "weaknesses", "nextActions"}, "review")
    if problem is not None:
        return problem
    for field in ("strengths", "weaknesses"):
        problem = _grounded_array_problem(
            f"review.{field}", review[field], SourceType.INTERVIEW, copilot_input
        )
        if problem is not None:
            return problem
    problem = _string_array_problem("review.nextActions", review["nextActions"])
    if problem is not None:
        return problem
    if observed_categories != set(InterviewQuestionCategory):
        return "E_INVALID_ENUM", "possibleQuestions do not contain every V1 category"
    return None


def _key_problem(value: dict[str, Any], expected: set[str], path: str) -> tuple[str, str] | None:
    missing = sorted(expected - set(value))
    if missing:
        return "C_MISSING_FIELD", f"{path} is missing fields: {', '.join(missing)}"
    extra = sorted(set(value) - expected)
    if extra:
        return "H_OTHER", f"{path} contains {len(extra)} unexpected field(s)"
    return None


def _grounded_array_problem(
    path: str,
    value: object,
    source_type: SourceType,
    copilot_input: CopilotInput,
) -> tuple[str, str] | None:
    if not isinstance(value, list):
        return "D_WRONG_TYPE", f"{path} must be an array"
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            return "D_WRONG_TYPE", f"{item_path} must be an object"
        problem = _key_problem(item, {"text", "sourceEvidence"}, item_path)
        if problem is not None:
            return problem
        if not isinstance(item["text"], str):
            return "D_WRONG_TYPE", f"{item_path}.text must be a string"
        problem = _evidence_problem(
            f"{item_path}.sourceEvidence",
            item["sourceEvidence"],
            source_type,
            copilot_input,
        )
        if problem is not None:
            return problem
    return None


def _evidence_problem(
    path: str,
    value: object,
    expected_source_type: SourceType,
    copilot_input: CopilotInput,
) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return "F_EVIDENCE_STRUCTURE", f"{path} must be an evidence object"
    if set(value) != {"text", "sourceType", "sourceId"}:
        return "F_EVIDENCE_STRUCTURE", f"{path} has invalid evidence fields"
    if not all(isinstance(value[field], str) and value[field].strip() for field in value):
        return "F_EVIDENCE_STRUCTURE", f"{path} evidence fields must be non-empty strings"
    if value["sourceType"] != expected_source_type.value:
        return "F_EVIDENCE_STRUCTURE", f"{path}.sourceType does not match the owning field"
    sources = {
        SourceType.JOB: copilot_input.job_sources,
        SourceType.RESUME: (
            (copilot_input.resume_source,) if copilot_input.resume_source is not None else ()
        ),
        SourceType.INTERVIEW: copilot_input.interview_sources,
    }[expected_source_type]
    matching_sources = [source for source in sources if source.id == value["sourceId"]]
    if not matching_sources:
        return "F_EVIDENCE_STRUCTURE", f"{path}.sourceId is not in the current allowed sources"
    if not any(_key(value["text"]) in _key(source.text) for source in matching_sources):
        return "F_EVIDENCE_STRUCTURE", f"{path}.text is not grounded in its declared source"
    return None


def _string_array_problem(path: str, value: object) -> tuple[str, str] | None:
    if not isinstance(value, list):
        return "D_WRONG_TYPE", f"{path} must be an array"
    if not all(isinstance(item, str) for item in value):
        return "D_WRONG_TYPE", f"{path} entries must be strings"
    return None


def _safe_shape(value: object) -> str:
    if isinstance(value, dict):
        known_keys = sorted(key for key in value if key in KNOWN_RESPONSE_FIELDS)
        fields = [f"{key}:{_type_name(value[key])}" for key in known_keys]
        unknown_count = len(value) - len(known_keys)
        if unknown_count:
            fields.append(f"unknownFields:{unknown_count}")
        return f"object{{{','.join(fields)}}}"
    return _type_name(value)


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return "unknown"


def _key(value: object) -> str:
    return "".join(str(value).casefold().split()) if isinstance(value, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
