import pytest

from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus


def test_initial_state(sample_run: IngestionRun) -> None:
    assert sample_run.status == RunStatus.PENDING
    assert sample_run.records_ingested is None


def test_start_transition(sample_run: IngestionRun) -> None:
    sample_run.start()
    assert sample_run.status == RunStatus.IN_PROGRESS


def test_start_from_non_pending_raises(sample_run: IngestionRun) -> None:
    sample_run.start()
    with pytest.raises(ValueError, match="Run can only be started from PENDING status."):
        sample_run.start()


def test_complete_transition(sample_run: IngestionRun) -> None:
    sample_run.start()
    sample_run.complete(records_ingested=42)
    assert sample_run.status == RunStatus.COMPLETED
    assert sample_run.records_ingested == 42


def test_complete_from_pending_raises(sample_run: IngestionRun) -> None:
    with pytest.raises(ValueError, match="Run can only be completed from IN_PROGRESS status."):
        sample_run.complete(records_ingested=10)


def test_complete_with_negative_records_raises(sample_run: IngestionRun) -> None:
    sample_run.start()
    with pytest.raises(ValueError, match="Records ingested cannot be negative."):
        sample_run.complete(records_ingested=-1)


def test_fail_transition(sample_run: IngestionRun) -> None:
    sample_run.start()
    sample_run.fail()
    assert sample_run.status == RunStatus.FAILED


def test_fail_from_pending_raises(sample_run: IngestionRun) -> None:
    with pytest.raises(ValueError, match="Run can only be failed from IN_PROGRESS status."):
        sample_run.fail()


def test_fail_from_completed_raises(sample_run: IngestionRun) -> None:
    sample_run.start()
    sample_run.complete(records_ingested=10)
    with pytest.raises(ValueError, match="Run can only be failed from IN_PROGRESS status."):
        sample_run.fail()
