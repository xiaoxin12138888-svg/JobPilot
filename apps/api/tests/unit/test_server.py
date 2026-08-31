from __future__ import annotations

import importlib

import pytest


def test_supported_server_uses_the_default_loopback_bind(monkeypatch) -> None:
    server = importlib.import_module("jobpilot_api.server")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    server.run(environment={})

    assert calls == [{"host": "127.0.0.1", "port": 8000, "reload": False}]


@pytest.mark.parametrize("bind_host", ["127.0.0.1", "::1"])
def test_supported_server_accepts_loopback_ip_literals(monkeypatch, bind_host: str) -> None:
    server = importlib.import_module("jobpilot_api.server")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    server.run(environment={"JOBPILOT_API_BIND_HOST": bind_host})

    assert calls[0]["host"] == bind_host


@pytest.mark.parametrize(
    "bind_host",
    ["0.0.0.0", "::", "192.168.1.20", "localhost", "api.example.invalid"],
)
def test_supported_server_rejects_non_loopback_before_calling_uvicorn(
    monkeypatch,
    bind_host: str,
) -> None:
    server = importlib.import_module("jobpilot_api.server")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    with pytest.raises(ValueError, match="loopback"):
        server.run(environment={"JOBPILOT_API_BIND_HOST": bind_host})

    assert calls == []
