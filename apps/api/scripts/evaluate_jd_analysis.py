from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobpilot_api.application.jd_analysis import JD_ANALYSIS_SYSTEM_PROMPT_V1  # noqa: E402
from jobpilot_api.config import ApiSettings  # noqa: E402
from jobpilot_api.domain.errors import DomainError  # noqa: E402
from jobpilot_api.domain.jd_analysis import (  # noqa: E402
    JDAnalysis,
    JDAnalysisInput,
    parse_and_ground_analysis,
)
from jobpilot_api.infrastructure.ai.openai_compatible import (  # noqa: E402
    OpenAICompatibleJDAnalysisProvider,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the real Prompt V1 JD analysis evaluation")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    samples = dataset.get("samples")
    if dataset.get("goldReviewStatus") != "human-reviewed":
        print("BLOCKED: gold labels are not marked human-reviewed", file=sys.stderr)
        return 2
    if not isinstance(samples, list) or len(samples) < 20:
        print("BLOCKED: evaluation dataset must contain at least 20 samples", file=sys.stderr)
        return 2
    settings = ApiSettings.from_environment().llm
    if settings is None:
        print("BLOCKED: Provider configuration is incomplete or invalid", file=sys.stderr)
        return 2

    provider = OpenAICompatibleJDAnalysisProvider(settings)
    valid = 0
    comparisons = []
    evidence_provided = 0
    evidence_grounded = 0
    for sample in samples:
        entry: dict[str, Any] = {"id": sample["id"], "schemaValid": False}
        try:
            analysis_input = JDAnalysisInput(
                title=sample["title"],
                company=sample["company"],
                description=sample["description"],
                location=sample.get("location"),
                salary_text=sample.get("salaryText"),
            )
            raw_content = provider.analyze(
                analysis_input,
                system_instruction=JD_ANALYSIS_SYSTEM_PROMPT_V1,
            )
            provided, grounded = _raw_evidence_counts(raw_content, sample["description"])
            evidence_provided += provided
            evidence_grounded += grounded
            result = parse_and_ground_analysis(raw_content, sample["description"])
            entry.update(_compare(result, sample["gold"]))
            entry["schemaValid"] = True
            entry["result"] = result.as_dict()
            valid += 1
        except (DomainError, KeyError, TypeError, json.JSONDecodeError):
            entry["error"] = "INVALID_OR_UNAVAILABLE"
        comparisons.append(entry)

    output = {
        "datasetVersion": dataset["datasetVersion"],
        "promptVersion": "v1",
        "sampleCount": len(samples),
        "metrics": {
            "schemaSuccess": {"valid": valid, "total": len(samples)},
            **_totals(comparisons),
            "evidenceGrounding": {
                "grounded": evidence_grounded,
                "provided": evidence_provided,
            },
            "unsupportedHallucinationCount": evidence_provided - evidence_grounded,
        },
        "samples": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


def _compare(result: JDAnalysis, gold: dict[str, list[str]]) -> dict[str, Any]:
    actual = {
        "responsibilities": [item.text for item in result.responsibilities],
        "mustHaveRequirements": [item.text for item in result.must_have_requirements],
        "preferredRequirements": [item.text for item in result.preferred_requirements],
        "skills": list(result.skills),
    }
    differences: dict[str, Any] = {}
    for field, values in actual.items():
        expected_set = {_key(value) for value in gold[field]}
        actual_set = {_key(value) for value in values}
        differences[f"{field}Omissions"] = sorted(expected_set - actual_set)
        differences[f"{field}FalseExtractions"] = sorted(actual_set - expected_set)
    differences["mustHaveMisclassifiedAsPreferred"] = sorted(
        {_key(value) for value in gold["mustHaveRequirements"]}
        & {_key(value) for value in actual["preferredRequirements"]}
    )
    differences["preferredMisclassifiedAsMustHave"] = sorted(
        {_key(value) for value in gold["preferredRequirements"]}
        & {_key(value) for value in actual["mustHaveRequirements"]}
    )
    return differences


def _raw_evidence_counts(raw_content: str, description: str) -> tuple[int, int]:
    payload = json.loads(raw_content)
    normalized_description = _key(description)
    evidence = []
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                evidence.extend(
                    item.get("evidence")
                    for item in value
                    if isinstance(item, dict) and isinstance(item.get("evidence"), str)
                )
    return len(evidence), sum(_key(value) in normalized_description for value in evidence)


def _totals(entries: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "responsibilitiesOmissions",
        "responsibilitiesFalseExtractions",
        "mustHaveRequirementsOmissions",
        "mustHaveRequirementsFalseExtractions",
        "preferredRequirementsOmissions",
        "preferredRequirementsFalseExtractions",
        "mustHaveMisclassifiedAsPreferred",
        "preferredMisclassifiedAsMustHave",
    )
    return {key: sum(len(entry.get(key, [])) for entry in entries) for key in keys}


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


if __name__ == "__main__":
    raise SystemExit(main())
