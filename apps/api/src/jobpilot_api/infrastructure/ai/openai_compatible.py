from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, OpenerDirector, ProxyHandler, Request, build_opener

from jobpilot_api.application.providers import CopilotRepairRequest
from jobpilot_api.config import LLMSettings
from jobpilot_api.domain.copilot import CopilotInput
from jobpilot_api.domain.errors import (
    AnalysisInvalidResponseDiagnostic,
    AnalysisInvalidResponseError,
    AnalysisProviderUnavailableError,
    AnalysisTimeoutError,
)
from jobpilot_api.domain.evidence_maps import EvidenceMapInput
from jobpilot_api.domain.jd_analysis import JDAnalysisInput

MAX_PROVIDER_RESPONSE_BYTES = 1_000_000


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class OpenAICompatibleJDAnalysisProvider:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        opener: OpenerDirector | Any | None = None,
    ) -> None:
        self._settings = settings
        self._opener = opener or build_opener(ProxyHandler({}), _RejectRedirectHandler())

    @property
    def model(self) -> str:
        return self._settings.model

    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str:
        return self._complete(analysis_input.as_provider_data(), system_instruction)

    def map_evidence(self, evidence_input: EvidenceMapInput, *, system_instruction: str) -> str:
        return self._complete(evidence_input.as_provider_data(), system_instruction)

    def generate_copilot(
        self,
        copilot_input: CopilotInput,
        *,
        system_instruction: str,
        repair: CopilotRepairRequest | None = None,
    ) -> str:
        return self._complete(
            copilot_input.as_provider_data(),
            system_instruction,
            expose_timeout=True,
            repair=repair,
        )

    def _complete(
        self,
        provider_data: object,
        system_instruction: str,
        *,
        expose_timeout: bool = False,
        repair: CopilotRepairRequest | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": json.dumps(
                    provider_data,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if repair is not None:
            messages.extend(
                [
                    {"role": "assistant", "content": repair.previous_response},
                    {"role": "user", "content": _repair_instruction(repair.validator_error)},
                ]
            )
        request_body = json.dumps(
            {
                "model": self._settings.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{self._settings.base_url}/chat/completions",
            data=request_body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._settings.timeout_seconds) as response:
                body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except (TimeoutError, URLError) as error:
            if expose_timeout and _is_timeout(error):
                raise AnalysisTimeoutError("AI 生成超时，请稍后重试") from None
            raise AnalysisProviderUnavailableError("AI 分析暂时不可用，请稍后重试") from None
        except (HTTPError, OSError):
            raise AnalysisProviderUnavailableError("AI 分析暂时不可用，请稍后重试") from None
        if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
            raise _invalid_response()
        try:
            payload = json.loads(body)
            choices = payload["choices"]
            content = choices[0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise _invalid_response() from None
        if not isinstance(content, str):
            raise _invalid_response()
        return content


def _invalid_response() -> AnalysisInvalidResponseError:
    return AnalysisInvalidResponseError(
        "AI 返回的分析结果无法验证，请稍后重试",
        diagnostic_code=AnalysisInvalidResponseDiagnostic.PROVIDER_ENVELOPE,
    )


def _is_timeout(error: TimeoutError | URLError) -> bool:
    return isinstance(error, TimeoutError) or isinstance(error.reason, TimeoutError)


def _repair_instruction(validator_error: str) -> str:
    safe_code = (
        validator_error
        if validator_error in {item.value for item in AnalysisInvalidResponseDiagnostic}
        else AnalysisInvalidResponseDiagnostic.SCHEMA_MISMATCH.value
    )
    return f"""Previous response failed schema validation: {safe_code}.
Return the same semantic answer using the required JSON schema.
Do not add new claims.
Do not add new evidence.
Return JSON only."""
