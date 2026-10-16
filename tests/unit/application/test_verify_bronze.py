from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.verify_bronze import VerifyBronze
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def test_verify_run_success() -> None:
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
    )
    repository.get.return_value = run

    expected_result = VerificationResult(
        run_id=run_id,
        status=VerificationStatus.VERIFIED,
        record_count=100,
    )
    bronze.verify.return_value = expected_result

    service = VerifyBronze(repository=repository, bronze=bronze)
    result = service.verify_run(run_id)

    assert result == expected_result
    repository.get.assert_called_once_with(run_id)
    bronze.verify.assert_called_once_with(run)


def test_verify_run_not_found_raises() -> None:
    repository = MagicMock()
    bronze = MagicMock()
    repository.get.return_value = None

    service = VerifyBronze(repository=repository, bronze=bronze)
    missing_id = uuid4()

    with pytest.raises(ValueError, match=f"Run with ID {missing_id} not found."):
        service.verify_run(missing_id)

    bronze.verify.assert_not_called()


def test_verify_date_filters_and_verifies() -> None:
    repository = MagicMock()
    bronze = MagicMock()

    day = date(2026, 6, 19)
    run1 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="tbmt", start_date=day, end_date_exclusive=date(2026, 6, 20)
        ),
    )
    run2 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="other", start_date=day, end_date_exclusive=date(2026, 6, 20)
        ),
    )
    repository.list_by_window.return_value = [run1, run2]

    res1 = VerificationResult(
        run_id=run1.run_id, status=VerificationStatus.VERIFIED, record_count=10
    )
    bronze.verify.return_value = res1

    service = VerifyBronze(repository=repository, bronze=bronze)
    results = service.verify_date(date=day, resource="tbmt")

    # Only run1 matches resource "tbmt"
    assert len(results) == 1
    assert results[0] == res1
    bronze.verify.assert_called_once_with(run1)
