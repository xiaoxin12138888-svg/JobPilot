from __future__ import annotations

import pytest

from jobpilot_api.config import ApiSettings


def test_api_settings_use_safe_local_defaults() -> None:
    settings = ApiSettings.from_environment({})

    assert settings.bind_host == "127.0.0.1"
    assert settings.cors_origins == ("http://127.0.0.1:5173",)
    assert settings.llm is None
    assert "database" not in repr(settings).lower()
    assert "auth" not in repr(settings).lower()


def test_api_settings_enable_llm_only_with_complete_valid_environment() -> None:
    settings = ApiSettings.from_environment(
        {
            "JOBPILOT_LLM_BASE_URL": "https://llm.example/v1/",
            "JOBPILOT_LLM_API_KEY": "private-value",
            "JOBPILOT_LLM_MODEL": "model-name",
        }
    )

    assert settings.llm is not None
    assert settings.llm.base_url == "https://llm.example/v1"
    assert settings.llm.model == "model-name"
    assert "private-value" not in repr(settings)


@pytest.mark.parametrize(
    "environment",
    [
        {"JOBPILOT_LLM_BASE_URL": "https://llm.example/v1"},
        {
            "JOBPILOT_LLM_BASE_URL": "https://llm.example/v1",
            "JOBPILOT_LLM_API_KEY": "key",
        },
        {
            "JOBPILOT_LLM_BASE_URL": "file:///tmp/provider",
            "JOBPILOT_LLM_API_KEY": "key",
            "JOBPILOT_LLM_MODEL": "model",
        },
        {
            "JOBPILOT_LLM_BASE_URL": "https://user:pass@llm.example/v1",
            "JOBPILOT_LLM_API_KEY": "key",
            "JOBPILOT_LLM_MODEL": "model",
        },
    ],
)
def test_incomplete_or_invalid_llm_environment_keeps_core_unconfigured(
    environment: dict[str, str],
) -> None:
    assert ApiSettings.from_environment(environment).llm is None


@pytest.mark.parametrize("bind_host", ["127.0.0.1", "::1"])
def test_api_settings_accept_ip_literal_loopback_bind_hosts(bind_host: str) -> None:
    settings = ApiSettings.from_environment({"JOBPILOT_API_BIND_HOST": bind_host})

    assert settings.bind_host == bind_host


@pytest.mark.parametrize(
    "bind_host",
    [
        "0.0.0.0",
        "::",
        "192.168.1.20",
        "localhost",
        "api.example.invalid",
        " 127.0.0.1 ",
    ],
)
def test_api_settings_reject_non_loopback_or_non_literal_bind_hosts(bind_host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        ApiSettings.from_environment({"JOBPILOT_API_BIND_HOST": bind_host})


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.invalid",
        "http://127.0.0.1:5173/",
        "http://127.0.0.1:5173/path",
        "http://127.0.0.1:5173?query=value",
        "http://127.0.0.1:5173#fragment",
        "http://user@127.0.0.1:5173",
        "null",
    ],
)
def test_api_settings_reject_non_exact_cors_origins(origin: str) -> None:
    with pytest.raises(ValueError, match="CORS origin"):
        ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": origin})


def test_api_settings_reject_duplicate_cors_origins() -> None:
    origin = "http://127.0.0.1:5173"

    with pytest.raises(ValueError, match="duplicate"):
        ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": f"{origin},{origin}"})


@pytest.mark.parametrize(
    "origin",
    [
        "http://192.168.1.20:5173",
        "https://web.example.invalid",
        "chrome-extension://not-a-valid-extension-id",
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf",
    ],
)
def test_api_settings_reject_nonlocal_cors_origins(origin: str) -> None:
    with pytest.raises(ValueError, match="CORS origin"):
        ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": origin})


def test_api_settings_accept_exact_loopback_web_origins() -> None:
    ipv4_origin = "http://127.0.0.1:5173"
    localhost_origin = "https://localhost:5173"

    settings = ApiSettings.from_environment(
        {"JOBPILOT_CORS_ORIGINS": f"{ipv4_origin},{localhost_origin}"}
    )

    assert settings.cors_origins == (ipv4_origin, localhost_origin)
