from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.recover_ingestion_run import (
    RecoverIngestionRun,
)
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def test_recover_run_not_found_raises() -> None:
    repository = MagicMock()
    bronze = MagicMock()
    repository.get.return_value = None

    service = RecoverIngestionRun(run_repository=repository, bronze=bronze)
    run_id = uuid4()

    with pytest.raises(ValueError, match=f"Run with ID {run_id} not found."):
        service.recover_run(run_id)


@pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.COMPLETED, RunStatus.FAILED])
def test_recover_run_not_in_progress_raises(status: RunStatus) -> None:
    repository = MagicMock()
    bronze = MagicMock()
    run_id = uuid4()

    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt",
            start_date=date(2026, 6, 19),
            end_date_exclusive=date(2026, 6, 20),
        ),
        status=status,
    )
    repository.get.return_value = run

    service = RecoverIngestionRun(run_repository=repository, bronze=bronze)

    with pytest.raises(ValueError, match="is not in IN_PROGRESS status and cannot be recovered."):
        service.recover_run(run_id)


def test_recover_run_success_marks_completed() -> None:
    repository = MagicMock()
    bronze = MagicMock()
    run_id = uuid4()

    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt",
            start_date=date(2026, 6, 19),
            end_date_exclusive=date(2026, 6, 20),
        ),
        status=RunStatus.IN_PROGRESS,
    )
    repository.get.return_value = run

    verification = VerificationResult(
        run_id=run_id,
        status=VerificationStatus.VERIFIED,
        record_count=150,
    )
    bronze.verify.return_value = verification

    service = RecoverIngestionRun(run_repository=repository, bronze=bronze)
    updated, result = service.recover_run(run_id)

    assert updated is True
    assert result == verification
    assert run.status == RunStatus.COMPLETED
    assert run.records_ingested == 150
    repository.update.assert_called_once_with(run)


def test_recover_run_failed_verification_marks_failed() -> None:
    repository = MagicMock()
    bronze = MagicMock()
    run_id = uuid4()

    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt",
            start_date=date(2026, 6, 19),
            end_date_exclusive=date(2026, 6, 20),
        ),
        status=RunStatus.IN_PROGRESS,
    )
    repository.get.return_value = run

    verification = VerificationResult(
        run_id=run_id,
        status=VerificationStatus.INVALID,
        reason="Checksum mismatch",
    )
    bronze.verify.return_value = verification

    service = RecoverIngestionRun(run_repository=repository, bronze=bronze)
    updated, result = service.recover_run(run_id)

    assert updated is True
    assert result == verification
    assert run.status == RunStatus.FAILED
    repository.update.assert_called_once_with(run)
