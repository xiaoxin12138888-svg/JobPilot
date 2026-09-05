from __future__ import annotations

from typing import Protocol

from jobpilot_api.domain.evidence_maps import EvidenceMapInput
from jobpilot_api.domain.jd_analysis import JDAnalysisInput


class JDAnalysisProvider(Protocol):
    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str: ...


class EvidenceMapProvider(Protocol):
    def map_evidence(self, evidence_input: EvidenceMapInput, *, system_instruction: str) -> str: ...
