from __future__ import annotations

import logging


class UvicornAccessQueryRedactionFilter(logging.Filter):
    """Keep request paths observable without logging query credentials."""

    def filter(self, record: logging.LogRecord) -> bool:
        arguments = record.args
        if not isinstance(arguments, tuple) or len(arguments) < 3:
            return False

        request_target = arguments[2]
        if not isinstance(request_target, str):
            return False

        redacted_target = request_target.partition("?")[0]
        record.args = (*arguments[:2], redacted_target, *arguments[3:])
        return True


def install_uvicorn_access_query_redaction() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    if any(isinstance(item, UvicornAccessQueryRedactionFilter) for item in access_logger.filters):
        return
    access_logger.addFilter(UvicornAccessQueryRedactionFilter())
