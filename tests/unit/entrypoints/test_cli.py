from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from typer.testing import CliRunner

from vn_procurement_lakehouse.entrypoints.cli import app
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.coverage import DayCoverage
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)

runner = CliRunner()


def test_ingest_unsupported_resource() -> None:
    result = runner.invoke(app, ["ingest", "pro", "--date", "2026-06-19"])
    assert result.exit_code != 0
    assert "Unsupported resource 'pro'" in result.output
    assert "project" in result.output


def test_ingest_range_unsupported_resource() -> None:
    result = runner.invoke(
        app, ["ingest-range", "unknown_res", "--start", "2026-06-19", "--end", "2026-06-20"]
    )
    assert result.exit_code != 0
    assert "Unsupported resource 'unknown_res'" in result.output


def test_verify_window_unsupported_resource() -> None:
    result = runner.invoke(app, ["bronze-verify-window", "invalid_res", "--date", "2026-06-19"])
    assert result.exit_code != 0
    assert "Unsupported resource 'invalid_res'" in result.output


def test_ingest_invalid_date_format() -> None:
    result = runner.invoke(app, ["ingest", "project", "--date", "19-06-2026"])
    assert result.exit_code != 0
    assert "Invalid date format" in result.output


def test_ingest_range_invalid_order() -> None:
    result = runner.invoke(
        app, ["ingest-range", "project", "--start", "2026-06-20", "--end", "2026-06-19"]
    )
    assert result.exit_code != 0
    assert "must be before end date" in result.output


def test_ingest_success() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=10,
        storage_uri="local:///data/test.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "project", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "Ingested 10 records" in result.output
    assert str(mock_batch.run_id) in result.output


def test_ingest_khlcnt_alias_plan_success() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=5,
        storage_uri="local:///data/khlcnt.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "plan", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "Ingested 5 records" in result.output
    window_arg = mock_service.ingestion_daily.execute.call_args[0][0]
    assert window_arg.resource == "khlcnt"


def test_ingest_tbmt_alias_notify_contractor_success() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=8,
        storage_uri="local:///data/tbmt.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "notify_contractor", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "Ingested 8 records" in result.output
    window_arg = mock_service.ingestion_daily.execute.call_args[0][0]
    assert window_arg.resource == "tbmt"


def test_ingest_kqlcnt_alias_contractor_result_success() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=12,
        storage_uri="local:///data/kqlcnt.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "contractor_result", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "Ingested 12 records" in result.output
    window_arg = mock_service.ingestion_daily.execute.call_args[0][0]
    assert window_arg.resource == "kqlcnt"


def test_ingest_bid_opening_alias_bbmt_success() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=3,
        storage_uri="local:///data/bid_opening.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "bbmt", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "Ingested 3 records" in result.output
    window_arg = mock_service.ingestion_daily.execute.call_args[0][0]
    assert window_arg.resource == "bid_opening"


def test_verify_run_command() -> None:
    run_id = uuid4()
    mock_result = VerificationResult(
        run_id=run_id,
        status=VerificationStatus.VERIFIED,
        record_count=25,
    )
    mock_service = MagicMock()
    mock_service.verify_bronze.verify_run.return_value = mock_result

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.verify_bronze_scope", fake_scope):
        result = runner.invoke(app, ["bronze-verify-run", str(run_id)])

    assert result.exit_code == 0
    assert "VERIFIED" in result.output
    assert "Record count: 25" in result.output


def test_recover_cancelled_by_user() -> None:
    run_id = uuid4()
    mock_service = MagicMock()

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.recover_ingestion_scope", fake_scope):
        # send "n" to confirmation prompt
        result = runner.invoke(app, ["bronze-recover", "--run-id", str(run_id)], input="n\n")

    assert result.exit_code == 0
    assert "Recovery cancelled." in result.output


def test_ingest_skipped() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=10,
        storage_uri="local:///data/test.jsonl",
        skipped=True,
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "project", "--date", "2026-06-19"])

    assert result.exit_code == 0
    assert "[SKIP]" in result.output
    assert "already verified" in result.output
    assert str(mock_batch.run_id) in result.output


def test_ingest_with_force() -> None:
    mock_batch = PublishedBatch(
        run_id=uuid4(),
        record_count=10,
        storage_uri="local:///data/test.jsonl",
        skipped=False,
    )
    mock_service = MagicMock()
    mock_service.ingestion_daily.execute.return_value = mock_batch

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(app, ["ingest", "project", "--date", "2026-06-19", "--force"])

    assert result.exit_code == 0
    assert "Ingested 10 records" in result.output
    _, kwargs = mock_service.ingestion_daily.execute.call_args
    assert kwargs.get("force") is True


def test_coverage_command() -> None:
    run_id = uuid4()
    mock_days = [
        DayCoverage(
            date=date(2026, 6, 1),
            status="VERIFIED",
            record_count=15,
            run_id=run_id,
            storage_uri="local:///bronze/tbmt/date=2026-06-01",
        ),
        DayCoverage(
            date=date(2026, 6, 2),
            status="MISSING",
            record_count=None,
            run_id=None,
            storage_uri=None,
        ),
    ]
    mock_service = MagicMock()
    mock_service.data_coverage.execute.return_value = mock_days

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.coverage_scope", fake_scope):
        result = runner.invoke(
            app, ["coverage", "tbmt", "--start", "2026-06-01", "--end", "2026-06-03"]
        )

    assert result.exit_code == 0
    assert "Bronze Data Coverage: TBMT" in result.output
    assert "2026-06-01" in result.output
    assert "VERIFIED" in result.output
    assert "2026-06-02" in result.output
    assert "MISSING" in result.output
    assert "Summary:" in result.output
    assert "1 verified" in result.output
    assert "1 missing" in result.output


def test_ingest_range_command_success() -> None:
    batch_day1 = PublishedBatch(
        run_id=uuid4(),
        record_count=10,
        storage_uri="local:///data/1.jsonl",
    )
    batch_day2 = PublishedBatch(
        run_id=uuid4(),
        record_count=20,
        storage_uri="local:///data/2.jsonl",
    )
    mock_service = MagicMock()
    mock_service.ingestion_range.execute.return_value = {
        date(2026, 6, 1): batch_day1,
        date(2026, 6, 2): batch_day2,
    }

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(
            app, ["ingest-range", "tbmt", "--start", "2026-06-01", "--end", "2026-06-03"]
        )

    assert result.exit_code == 0
    assert "Ingested 10 records for 2026-06-01" in result.output
    assert "Ingested 20 records for 2026-06-02" in result.output
    mock_service.ingestion_range.execute.assert_called_once()
    _, kwargs = mock_service.ingestion_range.execute.call_args
    assert kwargs.get("continue_on_error") is True


def test_ingest_range_command_reports_failed_days_note() -> None:
    batch_day1 = PublishedBatch(
        run_id=uuid4(),
        record_count=10,
        storage_uri="local:///data/1.jsonl",
    )
    mock_service = MagicMock()
    # 2 days requested, but only 1 day succeeded (1 day failed)
    mock_service.ingestion_range.execute.return_value = {
        date(2026, 6, 1): batch_day1,
    }

    @contextmanager
    def fake_scope():
        yield mock_service

    with patch("vn_procurement_lakehouse.entrypoints.cli.ingestion_scope", fake_scope):
        result = runner.invoke(
            app, ["ingest-range", "tbmt", "--start", "2026-06-01", "--end", "2026-06-03"]
        )

    assert result.exit_code == 0
    assert "Ingested 10 records for 2026-06-01" in result.output
    assert "Note: 1 of 2 days encountered errors" in result.output
