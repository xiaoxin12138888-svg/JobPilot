from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobpilot_api.application.copilot import PROMPTS  # noqa: E402
from jobpilot_api.config import ApiSettings  # noqa: E402
from jobpilot_api.domain.copilot import (  # noqa: E402
    CopilotInput,
    CopilotKind,
    CopilotSource,
    parse_copilot_result,
)
from jobpilot_api.domain.errors import DomainError  # noqa: E402
from jobpilot_api.infrastructure.ai.openai_compatible import (  # noqa: E402
    OpenAICompatibleJDAnalysisProvider,
)

INABILITY = re.compile(r"用户(?:不会|没有|不具备|无法)|候选人(?:不会|没有|不具备|无法)")
CERTAINTY = re.compile(r"一定会问|肯定会问|必问|面试官会问")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real AI Copilot evaluation")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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


def _key(value: object) -> str:
    return "".join(str(value).casefold().split()) if isinstance(value, str) else ""


if __name__ == "__main__":
    raise SystemExit(main())
