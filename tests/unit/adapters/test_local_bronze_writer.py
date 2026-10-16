import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.local_bronze_writer import (
    LocalBronzeWriter,
)
from vn_procurement_lakehouse.modules.ingestion.domain.models import (
    IngestionWindow,
)
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import VerificationStatus


def test_writer_publishes_manifest_and_data(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()

    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    records = [
        {"id": "IB001", "price": 100},
        {"id": "IB002", "price": 200},
    ]

    batch = writer.write(
        window,
        iter(records),
        run_id=run_id,
    )

    run_dir = tmp_path / "tbmt" / "date=2026-06-19" / "runs" / str(run_id)
    data_path = run_dir / "part-000.jsonl"
    manifest_path = run_dir / "manifest.json"

    assert batch.record_count == 2
    assert data_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == str(run_id)
    assert manifest["record_count"] == 2
    assert manifest["data_file"] == "part-000.jsonl"

    actual_checksum = hashlib.sha256(data_path.read_bytes()).hexdigest()
    assert manifest["sha256"] == actual_checksum

    # Không để lại temporary file sau khi thành công
    assert not list(run_dir.glob("*.tmp"))


def test_writer_raises_when_resource_is_invalid(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()

    # Resource containing special characters not matched by [a-zA-Z0-9_-]+
    # Since IngestionWindow allows non-empty strings, pass one that fails the regex
    window = IngestionWindow(
        resource="tbmt/../evil",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Invalid resource name"):
        writer.write(window, iter([]), run_id=run_id)


def test_writer_raises_when_run_directory_already_exists(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()

    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    # First write succeeds
    writer.write(window, iter([]), run_id=run_id)

    # Second write with same run_id must raise FileExistsError
    with pytest.raises(FileExistsError):
        writer.write(window, iter([]), run_id=run_id)


def test_verify_manifest_missing(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()
    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt", start_date=date(2026, 6, 19), end_date_exclusive=date(2026, 6, 20)
        ),
    )

    result = writer.verify(run)
    assert result.status == VerificationStatus.MISSING
    assert result.reason == "Manifest file is missing."


def test_verify_data_missing(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()
    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt", start_date=date(2026, 6, 19), end_date_exclusive=date(2026, 6, 20)
        ),
    )

    run_dir = tmp_path / "tbmt" / "date=2026-06-19" / "runs" / str(run_id)
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"sha256": "abc"}), encoding="utf-8")

    result = writer.verify(run)
    assert result.status == VerificationStatus.MISSING
    assert result.reason == "Data file is missing."


def test_verify_manifest_no_checksum(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()
    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt", start_date=date(2026, 6, 19), end_date_exclusive=date(2026, 6, 20)
        ),
    )

    run_dir = tmp_path / "tbmt" / "date=2026-06-19" / "runs" / str(run_id)
    run_dir.mkdir(parents=True)
    (run_dir / "part-000.jsonl").write_bytes(b"hello")
    (run_dir / "manifest.json").write_text(json.dumps({}), encoding="utf-8")

    result = writer.verify(run)
    assert result.status == VerificationStatus.INVALID
    assert result.reason == "Manifest file does not contain a checksum."


def test_verify_checksum_mismatch(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()
    run = IngestionRun(
        run_id=run_id,
        window=IngestionWindow(
            resource="tbmt", start_date=date(2026, 6, 19), end_date_exclusive=date(2026, 6, 20)
        ),
    )

    run_dir = tmp_path / "tbmt" / "date=2026-06-19" / "runs" / str(run_id)
    run_dir.mkdir(parents=True)
    (run_dir / "part-000.jsonl").write_bytes(b"hello")
    (run_dir / "manifest.json").write_text(json.dumps({"sha256": "wrong_hash"}), encoding="utf-8")

    result = writer.verify(run)
    assert result.status == VerificationStatus.INVALID
    assert result.reason == "Checksum mismatch between manifest and data file."


def test_verify_success(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(base_path=tmp_path)
    run_id = uuid4()
    window = IngestionWindow(
        resource="tbmt", start_date=date(2026, 6, 19), end_date_exclusive=date(2026, 6, 20)
    )

    writer.write(window, iter([{"a": 1}, {"b": 2}]), run_id=run_id)

    run = IngestionRun(run_id=run_id, window=window)
    result = writer.verify(run)

    assert result.status == VerificationStatus.VERIFIED
    assert result.record_count == 2
