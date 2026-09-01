from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_supported_server_initializes_sqlite_before_using_the_default_loopback_bind(
    monkeypatch,
    tmp_path: Path,
) -> None:
    server = importlib.import_module("jobpilot_api.server")
    database_path = tmp_path / "runtime-data" / "jobpilot.db"
    events: list[tuple[str, object]] = []
    monkeypatch.setattr(
        server,
        "initialize_database",
        lambda path: events.append(("database", path)),
    )
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda *args, **kwargs: events.append(("uvicorn", kwargs)),
    )

    server.run(environment={}, database_path=database_path)

    assert events == [
        ("database", database_path),
        ("uvicorn", {"host": "127.0.0.1", "port": 8000, "reload": False}),
    ]


@pytest.mark.parametrize("bind_host", ["127.0.0.1", "::1"])
def test_supported_server_accepts_loopback_ip_literals(
    monkeypatch,
    tmp_path: Path,
    bind_host: str,
) -> None:
    server = importlib.import_module("jobpilot_api.server")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(server, "initialize_database", lambda path: None)
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    server.run(
        environment={"JOBPILOT_API_BIND_HOST": bind_host},
        database_path=tmp_path / "jobpilot.db",
    )

    assert calls[0]["host"] == bind_host


@pytest.mark.parametrize(
    "bind_host",
    ["0.0.0.0", "::", "192.168.1.20", "localhost", "api.example.invalid"],
)
def test_supported_server_rejects_non_loopback_before_calling_uvicorn(
    monkeypatch,
    tmp_path: Path,
    bind_host: str,
) -> None:
    server = importlib.import_module("jobpilot_api.server")
    calls: list[dict[str, object]] = []
    initialized: list[Path] = []
    monkeypatch.setattr(server, "initialize_database", initialized.append)
    monkeypatch.setattr(server.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    with pytest.raises(ValueError, match="loopback"):
        server.run(
            environment={"JOBPILOT_API_BIND_HOST": bind_host},
            database_path=tmp_path / "jobpilot.db",
        )

    assert calls == []
    assert initialized == []
