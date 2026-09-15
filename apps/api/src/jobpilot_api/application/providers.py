from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jobpilot_api.domain.copilot import CopilotInput
from jobpilot_api.domain.evidence_maps import EvidenceMapInput
from jobpilot_api.domain.jd_analysis import JDAnalysisInput


class JDAnalysisProvider(Protocol):
    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str: ...


class EvidenceMapProvider(Protocol):
    def map_evidence(self, evidence_input: EvidenceMapInput, *, system_instruction: str) -> str: ...


@dataclass(frozen=True, slots=True)
class CopilotRepairRequest:
    previous_response: str
    validator_error: str


class CopilotProvider(Protocol):
    @property
    def model(self) -> str: ...

    def generate_copilot(
        self,
        copilot_input: CopilotInput,
        *,
        system_instruction: str,
        repair: CopilotRepairRequest | None = None,
    ) -> str: ...
