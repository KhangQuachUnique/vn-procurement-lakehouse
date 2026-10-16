from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def test_ingest_daily_window_happy_path(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    raw_records = [{"id": "IB001"}, {"id": "IB002"}]
    source.fetch.return_value = raw_records

    expected_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=2,
        storage_uri="mock://bronze/path",
    )
    writer.write.return_value = expected_batch

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    batch = service.execute(sample_window)

    assert batch == expected_batch
    source.fetch.assert_called_once_with(sample_window)
    writer.write.assert_called_once()
    repository.create.assert_called_once()
    # Updated twice: once to IN_PROGRESS, once to COMPLETED
    assert repository.update.call_count == 2


def test_source_failure_marks_run_failed(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    source.fetch.side_effect = RuntimeError("API unavailable")

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    with pytest.raises(RuntimeError, match="API unavailable"):
        service.execute(sample_window)

    repository.create.assert_called_once()
    assert repository.update.call_count == 2
    writer.write.assert_not_called()


def test_writer_failure_marks_run_failed(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    source.fetch.return_value = [{"id": "IB001"}]
    writer.write.side_effect = OSError("Bronze storage unavailable")

    history = []
    repository.create.side_effect = lambda run: history.append(("create", run.status))
    repository.update.side_effect = lambda run: history.append(("update", run.status))

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    with pytest.raises(OSError, match="Bronze storage unavailable"):
        service.execute(sample_window)

    assert [status for _, status in history] == [
        RunStatus.PENDING,
        RunStatus.IN_PROGRESS,
        RunStatus.FAILED,
    ]
    source.fetch.assert_called_once_with(sample_window)
    writer.write.assert_called_once()


def test_repository_failure_preserves_original_error(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    source.fetch.side_effect = RuntimeError("API unavailable")

    def update_side_effect(run):
        if run.status == RunStatus.FAILED:
            raise ConnectionError("PostgreSQL unavailable")

    repository.update.side_effect = update_side_effect

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    with pytest.raises(RuntimeError, match="API unavailable"):
        service.execute(sample_window)

    repository.create.assert_called_once()
    assert repository.update.call_count == 2
    writer.write.assert_not_called()


def test_ingest_daily_window_skips_when_already_verified(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    existing_run = IngestionRun(
        run_id=uuid4(),
        window=sample_window,
        status=RunStatus.COMPLETED,
        records_ingested=42,
    )
    repository.list_by_window.return_value = [existing_run]
    writer.verify.return_value = VerificationResult(
        run_id=existing_run.run_id,
        status=VerificationStatus.VERIFIED,
        record_count=42,
    )

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    batch = service.execute(sample_window, force=False)

    assert batch.skipped is True
    assert batch.run_id == existing_run.run_id
    assert batch.record_count == 42
    source.fetch.assert_not_called()
    writer.write.assert_not_called()
    repository.create.assert_not_called()


def test_ingest_daily_window_forces_reingest(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    existing_run = IngestionRun(
        run_id=uuid4(),
        window=sample_window,
        status=RunStatus.COMPLETED,
        records_ingested=42,
    )
    repository.list_by_window.return_value = [existing_run]
    writer.verify.return_value = VerificationResult(
        run_id=existing_run.run_id,
        status=VerificationStatus.VERIFIED,
        record_count=42,
    )

    source.fetch.return_value = [{"id": "IB001"}]
    expected_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=1,
        storage_uri="mock://bronze/new",
        skipped=False,
    )
    writer.write.return_value = expected_batch

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    batch = service.execute(sample_window, force=True)

    assert batch.skipped is False
    source.fetch.assert_called_once_with(sample_window)
    writer.write.assert_called_once()
    repository.create.assert_called_once()


def test_ingest_daily_window_on_record_progress(sample_window: IngestionWindow) -> None:
    source = MagicMock()
    writer = MagicMock()
    repository = MagicMock()

    source.fetch.return_value = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    expected_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=3,
        storage_uri="mock://bronze/path",
    )

    def write_side_effect(window, records, run_id):
        # consume generator to trigger counting
        list(records)
        return expected_batch

    writer.write.side_effect = write_side_effect

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    recorded_counts = []
    batch = service.execute(
        sample_window, on_record=lambda count: recorded_counts.append(count)
    )

    assert batch == expected_batch
    assert recorded_counts == [1, 2, 3]
