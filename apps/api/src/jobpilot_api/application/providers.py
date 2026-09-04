from __future__ import annotations

from typing import Protocol

from jobpilot_api.domain.jd_analysis import JDAnalysisInput


class JDAnalysisProvider(Protocol):
    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str: ...
