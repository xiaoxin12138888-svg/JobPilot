from jobpilot_api.infrastructure.database.engine import create_database_engine


def test_database_engine_hides_bound_parameters() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://postgres:password@db.example.invalid/jobpilot"
    )

    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()
