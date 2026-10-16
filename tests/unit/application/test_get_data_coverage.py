from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.get_data_coverage import (
    GetDataCoverage,
    iter_dates,
)
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)


def test_iter_dates_invalid_range():
    with pytest.raises(ValueError, match="Start date must be before end date exclusive."):
        list(iter_dates(date(2026, 1, 5), date(2026, 1, 5)))


def test_get_data_coverage_mixed_statuses():
    repository = MagicMock()
    bronze = MagicMock()
    bronze.base_path = "mock/bronze"

    # Day 1: 2026-06-01 -> VERIFIED
    run_day1 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="kqlcnt",
            start_date=date(2026, 6, 1),
            end_date_exclusive=date(2026, 6, 2),
        ),
        status=RunStatus.COMPLETED,
        records_ingested=15,
    )

    # Day 2: 2026-06-02 -> FAILED
    run_day2 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="kqlcnt",
            start_date=date(2026, 6, 2),
            end_date_exclusive=date(2026, 6, 3),
        ),
        status=RunStatus.FAILED,
        records_ingested=0,
    )

    repository.list_by_window.return_value = [run_day1, run_day2]
    bronze.verify.side_effect = lambda run: (
        VerificationResult(
            run_id=run.run_id,
            status=VerificationStatus.VERIFIED,
            record_count=15,
        )
        if run.run_id == run_day1.run_id
        else VerificationResult(
            run_id=run.run_id,
            status=VerificationStatus.MISSING,
        )
    )

    service = GetDataCoverage(repository=repository, bronze=bronze)
    report = service.execute(
        resource="kqlcnt",
        start_date=date(2026, 6, 1),
        end_date_exclusive=date(2026, 6, 4),  # Day 3 is missing!
    )

    assert report.resource == "kqlcnt"
    assert report.total_days == 3
    assert report.verified_days == 1
    assert report.failed_days == 1
    assert report.missing_days == 1

    assert report.days[0].date == date(2026, 6, 1)
    assert report.days[0].status == "VERIFIED"
    assert report.days[0].record_count == 15
    assert report.days[0].run_id == run_day1.run_id

    assert report.days[1].date == date(2026, 6, 2)
    assert report.days[1].status == "FAILED"

    assert report.days[2].date == date(2026, 6, 3)
    assert report.days[2].status == "MISSING"


def test_get_data_coverage_missing_only():
    repository = MagicMock()
    bronze = MagicMock()

    run_day1 = IngestionRun(
        run_id=uuid4(),
        window=IngestionWindow(
            resource="kqlcnt",
            start_date=date(2026, 6, 1),
            end_date_exclusive=date(2026, 6, 2),
        ),
        status=RunStatus.COMPLETED,
        records_ingested=15,
    )
    repository.list_by_window.return_value = [run_day1]
    bronze.verify.return_value = VerificationResult(
        run_id=run_day1.run_id,
        status=VerificationStatus.VERIFIED,
        record_count=15,
    )

    service = GetDataCoverage(repository=repository, bronze=bronze)
    report = service.execute(
        resource="kqlcnt",
        start_date=date(2026, 6, 1),
        end_date_exclusive=date(2026, 6, 3),  # Day 2 missing
        missing_only=True,
    )

    assert len(report.days) == 1
    assert report.days[0].date == date(2026, 6, 2)
    assert report.days[0].status == "MISSING"
