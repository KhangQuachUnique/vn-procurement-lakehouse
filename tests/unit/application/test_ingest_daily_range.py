from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_range import (
    IngestDateRange,
    iter_daily_windows,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch


def test_iter_daily_windows_yields_consecutive_days() -> None:
    windows = list(
        iter_daily_windows(
            resource="tbmt",
            start_date=date(2026, 6, 1),
            end_date_exclusive=date(2026, 6, 4),
        )
    )

    assert len(windows) == 3
    assert windows[0].start_date == date(2026, 6, 1)
    assert windows[0].end_date_exclusive == date(2026, 6, 2)
    assert windows[1].start_date == date(2026, 6, 2)
    assert windows[1].end_date_exclusive == date(2026, 6, 3)
    assert windows[2].start_date == date(2026, 6, 3)
    assert windows[2].end_date_exclusive == date(2026, 6, 4)


def test_iter_daily_windows_invalid_range_raises() -> None:
    with pytest.raises(ValueError, match="Start date must be before end date exclusive."):
        list(
            iter_daily_windows(
                resource="tbmt",
                start_date=date(2026, 6, 5),
                end_date_exclusive=date(2026, 6, 5),
            )
        )


def test_ingest_date_range_executes_each_day() -> None:
    ingest_daily_mock = MagicMock()
    batch_day1 = PublishedBatch(run_id=uuid4(), record_count=10, storage_uri="s3://1")
    batch_day2 = PublishedBatch(run_id=uuid4(), record_count=20, storage_uri="s3://2")

    ingest_daily_mock.execute.side_effect = [batch_day1, batch_day2]

    service = IngestDateRange(ingest_daily=ingest_daily_mock)
    results = service.execute(
        resource="tbmt",
        start_date=date(2026, 6, 1),
        end_date_exclusive=date(2026, 6, 3),
    )

    assert len(results) == 2
    assert results[date(2026, 6, 1)] == batch_day1
    assert results[date(2026, 6, 2)] == batch_day2
    assert ingest_daily_mock.execute.call_count == 2


def test_ingest_date_range_passes_force_and_on_record() -> None:
    ingest_daily_mock = MagicMock()
    batch = PublishedBatch(run_id=uuid4(), record_count=5, storage_uri="s3://1")
    ingest_daily_mock.execute.return_value = batch

    service = IngestDateRange(ingest_daily=ingest_daily_mock)
    mock_on_record = MagicMock()
    service.execute(
        resource="tbmt",
        start_date=date(2026, 6, 1),
        end_date_exclusive=date(2026, 6, 2),
        force=True,
        on_record=mock_on_record,
    )

    ingest_daily_mock.execute.assert_called_once()
    _, kwargs = ingest_daily_mock.execute.call_args
    assert kwargs.get("force") is True
    assert kwargs.get("on_record") is mock_on_record
