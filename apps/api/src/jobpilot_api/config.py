import os
from collections.abc import Mapping
from dataclasses import dataclass

DEVELOPMENT_WEB_ORIGIN = "http://localhost:5173"
VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})


@dataclass(frozen=True)
class ApiSettings:
    environment: str
    cors_origins: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"Unsupported JOBPILOT_ENVIRONMENT: {self.environment}")
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not allowed")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "ApiSettings":
        values = os.environ if environment is None else environment
        name = values.get("JOBPILOT_ENVIRONMENT", "development").strip().lower()
        configured_origins = values.get("JOBPILOT_CORS_ORIGINS")

        if configured_origins is None:
            origins = (DEVELOPMENT_WEB_ORIGIN,) if name == "development" else ()
        else:
            origins = tuple(
                origin.strip() for origin in configured_origins.split(",") if origin.strip()
            )

        return cls(environment=name, cors_origins=origins)
