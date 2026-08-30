from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from jobpilot_api.infrastructure.database.models import IdentityRecord, UserRecord


def _add_identity(
    session: Session,
    user: UserRecord,
    *,
    issuer: str = "https://tenant.example.invalid/",
    subject: str = "auth0|subject-1",
) -> IdentityRecord:
    session.flush()
    identity = IdentityRecord(user_id=user.id, issuer=issuer, subject=subject)
    session.add(identity)
    return identity


def test_user_and_identity_round_trip_with_minimum_profile(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        user = UserRecord(email="person@example.com")
        session.add(user)
        identity = _add_identity(session, user)
        session.commit()
        user_id = user.id
        identity_id = identity.id

    with Session(migrated_engine) as session:
        stored_user = session.get(UserRecord, user_id)
        stored_identity = session.get(IdentityRecord, identity_id)

        assert stored_user is not None
        assert isinstance(stored_user.id, UUID)
        assert stored_user.email == "person@example.com"
        assert stored_user.display_name is None
        assert stored_user.locale is None
        assert stored_user.time_zone is None
        assert stored_user.account_status == "active"
        assert stored_user.deletion_requested_at is None
        assert stored_user.created_at.utcoffset() is not None
        assert stored_user.updated_at.utcoffset() is not None
        assert stored_identity is not None
        assert stored_identity.user_id == stored_user.id
        assert stored_identity.issuer == "https://tenant.example.invalid/"
        assert stored_identity.subject == "auth0|subject-1"
        assert stored_identity.created_at.utcoffset() is not None
        assert stored_identity.updated_at.utcoffset() is not None


def test_user_email_is_unique(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        session.add(UserRecord(email="normalized@example.com"))
        session.commit()

        session.add(UserRecord(email="normalized@example.com"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_identity_issuer_and_subject_are_unique_together(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        first_user = UserRecord(email="first@example.com")
        session.add(first_user)
        _add_identity(session, first_user)
        session.commit()

        second_user = UserRecord(email="second@example.com")
        session.add(second_user)
        _add_identity(session, second_user)
        with pytest.raises(IntegrityError):
            session.commit()


def test_identity_subject_is_case_sensitive(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        first_user = UserRecord(email="first@example.com")
        session.add(first_user)
        _add_identity(session, first_user, subject="auth0|AbC")

        second_user = UserRecord(email="second@example.com")
        session.add(second_user)
        _add_identity(session, second_user, subject="auth0|abc")
        session.commit()

        identity_count = session.scalar(select(func.count()).select_from(IdentityRecord))
        assert identity_count == 2


def test_deleting_user_cascades_to_identity(migrated_engine: Engine) -> None:
    with Session(migrated_engine) as session:
        user = UserRecord(email="person@example.com")
        session.add(user)
        _add_identity(session, user)
        session.commit()

        session.delete(user)
        session.commit()

        identity_count = session.scalar(select(func.count()).select_from(IdentityRecord))
        assert identity_count == 0


@pytest.mark.parametrize(
    ("account_status", "deletion_requested_at"),
    [
        ("active", datetime(2026, 8, 30, tzinfo=UTC)),
        ("deletion_pending", None),
        ("unsupported", None),
    ],
)
def test_user_deletion_state_constraints_reject_invalid_combinations(
    migrated_engine: Engine,
    account_status: str,
    deletion_requested_at: datetime | None,
) -> None:
    with Session(migrated_engine) as session:
        session.add(
            UserRecord(
                email="person@example.com",
                account_status=account_status,
                deletion_requested_at=deletion_requested_at,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_duplicate_identity_race_leaves_one_user_and_identity(migrated_engine: Engine) -> None:
    insertion_barrier = Barrier(2)

    def insert_identity(email: str) -> str:
        with Session(migrated_engine) as session:
            user = UserRecord(email=email)
            session.add(user)
            session.flush()
            insertion_barrier.wait(timeout=5)
            session.add(
                IdentityRecord(
                    user_id=user.id,
                    issuer="https://tenant.example.invalid/",
                    subject="auth0|same-subject",
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return "conflict"
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(insert_identity, ["first@example.com", "second@example.com"]))

    assert sorted(outcomes) == ["committed", "conflict"]
    with Session(migrated_engine) as session:
        user_count = session.scalar(select(func.count()).select_from(UserRecord))
        identity_count = session.scalar(select(func.count()).select_from(IdentityRecord))
        assert user_count == 1
        assert identity_count == 1
