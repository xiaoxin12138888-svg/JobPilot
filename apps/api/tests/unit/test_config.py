from __future__ import annotations

import pytest

from jobpilot_api.config import ApiSettings


def test_api_settings_use_safe_local_defaults() -> None:
    settings = ApiSettings.from_environment({})

    assert settings.bind_host == "127.0.0.1"
    assert settings.cors_origins == ("http://127.0.0.1:5173",)
    assert "database" not in repr(settings).lower()
    assert "auth" not in repr(settings).lower()


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
    ],
)
def test_api_settings_reject_nonlocal_cors_origins(origin: str) -> None:
    with pytest.raises(ValueError, match="CORS origin"):
        ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": origin})


def test_api_settings_accept_exact_web_and_extension_origins() -> None:
    web_origin = "http://127.0.0.1:5173"
    extension_origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"

    settings = ApiSettings.from_environment(
        {"JOBPILOT_CORS_ORIGINS": f"{web_origin},{extension_origin}"}
    )

    assert settings.cors_origins == (web_origin, extension_origin)
