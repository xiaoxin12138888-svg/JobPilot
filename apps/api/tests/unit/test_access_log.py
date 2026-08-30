from __future__ import annotations

import io
import logging

from jobpilot_api.api.access_log import install_uvicorn_access_query_redaction


def test_uvicorn_access_log_keeps_path_and_redacts_every_query_value() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    previous_disabled = access_logger.disabled
    previous_level = access_logger.level
    previous_propagate = access_logger.propagate
    access_logger.disabled = False
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    access_logger.addHandler(handler)
    install_uvicorn_access_query_redaction()

    try:
        access_logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1:54321",
            "GET",
            (
                "/api/v1/auth/web/callback?code=private-code&state=private-state"
                "&error_description=private-provider-detail"
            ),
            "1.1",
            303,
        )
    finally:
        access_logger.removeHandler(handler)
        access_logger.disabled = previous_disabled
        access_logger.setLevel(previous_level)
        access_logger.propagate = previous_propagate

    rendered = output.getvalue()
    assert "/api/v1/auth/web/callback" in rendered
    assert "private-code" not in rendered
    assert "private-state" not in rendered
    assert "private-provider-detail" not in rendered
