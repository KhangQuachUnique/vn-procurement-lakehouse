from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.models import IngestionRunRow
from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.run_repository import (
    PostgresRunRepository,
)
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

pytestmark = pytest.mark.integration


def test_run_repository_crud_and_transitions(
    db_session_factory: sessionmaker[Session],
) -> None:
    repository = PostgresRunRepository(db_session_factory)
    start_date = date(2026, 6, 19)

    run = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=1),
        ),
    )

    try:
        # 1. CREATE
        repository.create(run)
        stored = repository.get(run.run_id)

        assert stored is not None
        assert stored.status == RunStatus.PENDING
        assert stored.run_id == run.run_id
        assert stored.window == run.window

        # 2. UPDATE: pending -> in_progress
        run.start()
        repository.update(run)

        stored = repository.get(run.run_id)
        assert stored is not None
        assert stored.status == RunStatus.IN_PROGRESS
        assert stored.records_ingested is None

        # 3. UPDATE: in_progress -> completed
        run.complete(10)
        repository.update(run)

        stored = repository.get(run.run_id)
        assert stored is not None
        assert stored.status == RunStatus.COMPLETED
        assert stored.records_ingested == 10

    finally:
        with db_session_factory.begin() as session:
            session.execute(delete(IngestionRunRow).where(IngestionRunRow.run_id == run.run_id))


def test_run_repository_list_by_window(
    db_session_factory: sessionmaker[Session],
) -> None:
    repository = PostgresRunRepository(db_session_factory)
    start_date = date(2026, 6, 21)

    run1 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=1),
        ),
    )
    run2 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt",
            start_date=start_date + timedelta(days=1),
            end_date_exclusive=start_date + timedelta(days=2),
        ),
    )

    try:
        repository.create(run1)
        repository.create(run2)

        runs = repository.list_by_window(
            resource="tbmt",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=2),
        )

        run_ids = [r.run_id for r in runs]
        assert run1.run_id in run_ids
        assert run2.run_id in run_ids

        # Query different resource returns empty
        empty_runs = repository.list_by_window(
            resource="other_resource",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=2),
        )
        assert len(empty_runs) == 0

    finally:
        with db_session_factory.begin() as session:
            session.execute(
                delete(IngestionRunRow).where(
                    IngestionRunRow.run_id.in_([run1.run_id, run2.run_id])
                )
            )


def test_run_repository_complete_if_running(
    db_session_factory: sessionmaker[Session],
) -> None:
    repository = PostgresRunRepository(db_session_factory)
    start_date = date(2026, 6, 25)

    run = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=1),
        ),
    )

    try:
        repository.create(run)

        # Still in PENDING, complete_if_running should return False
        assert repository.complete_if_running(run.run_id, records_ingested=5) is False

        # Transition to IN_PROGRESS
        run.start()
        repository.update(run)

        # Now in IN_PROGRESS, complete_if_running should succeed
        assert repository.complete_if_running(run.run_id, records_ingested=15) is True

        # Verify state in DB
        stored = repository.get(run.run_id)
        assert stored is not None
        assert stored.status == RunStatus.COMPLETED
        assert stored.records_ingested == 15

        # Calling again should return False because it's no longer IN_PROGRESS
        assert repository.complete_if_running(run.run_id, records_ingested=20) is False

        with pytest.raises(ValueError, match="records_ingested must be a non-negative integer."):
            repository.complete_if_running(run.run_id, records_ingested=-5)

    finally:
        with db_session_factory.begin() as session:
            session.execute(delete(IngestionRunRow).where(IngestionRunRow.run_id == run.run_id))


def test_run_repository_fail_with_error_message(
    db_session_factory: sessionmaker[Session],
) -> None:
    repository = PostgresRunRepository(db_session_factory)
    start_date = date(2026, 6, 28)

    run = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt",
            start_date=start_date,
            end_date_exclusive=start_date + timedelta(days=1),
        ),
    )

    try:
        repository.create(run)
        run.start()
        run.fail(error_message="HTTP 500: Database connection error")
        repository.update(run)

        stored = repository.get(run.run_id)
        assert stored is not None
        assert stored.status == RunStatus.FAILED
        assert stored.error_message == "HTTP 500: Database connection error"
    finally:
        with db_session_factory.begin() as session:
            session.execute(delete(IngestionRunRow).where(IngestionRunRow.run_id == run.run_id))

