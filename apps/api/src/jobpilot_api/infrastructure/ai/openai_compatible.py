from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from jobpilot_api.config import LLMSettings
from jobpilot_api.domain.errors import (
    AnalysisInvalidResponseError,
    AnalysisProviderUnavailableError,
)
from jobpilot_api.domain.jd_analysis import JDAnalysisInput

MAX_PROVIDER_RESPONSE_BYTES = 1_000_000


class OpenAICompatibleJDAnalysisProvider:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        opener: OpenerDirector | Any | None = None,
    ) -> None:
        self._settings = settings
        self._opener = opener or build_opener(ProxyHandler({}))

    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str:
        request_body = json.dumps(
            {
                "model": self._settings.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": json.dumps(
                            analysis_input.as_provider_data(),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
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
        except (HTTPError, URLError, TimeoutError, OSError):
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
    return AnalysisInvalidResponseError("AI 返回的分析结果无法验证，请稍后重试")
