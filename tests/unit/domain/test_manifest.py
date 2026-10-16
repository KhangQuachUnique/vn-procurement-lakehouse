from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.domain.manifest import BronzeManifest

VALID_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_valid_manifest() -> None:
    manifest = BronzeManifest(
        schema_version=1,
        run_id=uuid4(),
        resource="tbmt",
        window_start=date(2026, 6, 19),
        window_end_exclusive=date(2026, 6, 20),
        record_count=100,
        data_file="part-000.jsonl",
        sha256=VALID_SHA256,
        created_at=datetime.now(UTC),
    )

    assert manifest.schema_version == 1
    assert manifest.record_count == 100
    assert manifest.data_file == "part-000.jsonl"


def test_invalid_schema_version() -> None:
    with pytest.raises(ValueError, match="Unsupported manifest schema version"):
        BronzeManifest(
            schema_version=2,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=10,
            data_file="part-000.jsonl",
            sha256=VALID_SHA256,
            created_at=datetime.now(UTC),
        )


def test_empty_resource() -> None:
    with pytest.raises(ValueError, match="Resource must not be empty"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="   ",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=10,
            data_file="part-000.jsonl",
            sha256=VALID_SHA256,
            created_at=datetime.now(UTC),
        )


def test_invalid_window_duration() -> None:
    with pytest.raises(ValueError, match="Ingestion window must cover exactly one day"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 21),  # 2 days
            record_count=10,
            data_file="part-000.jsonl",
            sha256=VALID_SHA256,
            created_at=datetime.now(UTC),
        )


def test_negative_record_count() -> None:
    with pytest.raises(ValueError, match="Record count must be non-negative"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=-1,
            data_file="part-000.jsonl",
            sha256=VALID_SHA256,
            created_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "invalid_path",
    [
        "",
        "   ",
        "/absolute/path/file.jsonl",
        "../traversal.jsonl",
        "sub/../../secret.jsonl",
        "windows\\path.jsonl",
    ],
)
def test_invalid_data_file_paths(invalid_path: str) -> None:
    with pytest.raises(ValueError, match="Invalid data file path"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=10,
            data_file=invalid_path,
            sha256=VALID_SHA256,
            created_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "invalid_sha",
    [
        "not_a_sha",
        "e3b0c442",  # too short
        "g" * 64,  # invalid hex characters
    ],
)
def test_invalid_sha256(invalid_sha: str) -> None:
    with pytest.raises(ValueError, match="Invalid SHA-256 checksum"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=10,
            data_file="part-000.jsonl",
            sha256=invalid_sha,
            created_at=datetime.now(UTC),
        )


def test_naive_created_at() -> None:
    with pytest.raises(ValueError, match="created_at must be timezone-aware"):
        BronzeManifest(
            schema_version=1,
            run_id=uuid4(),
            resource="tbmt",
            window_start=date(2026, 6, 19),
            window_end_exclusive=date(2026, 6, 20),
            record_count=10,
            data_file="part-000.jsonl",
            sha256=VALID_SHA256,
            created_at=datetime(2026, 6, 19, 12, 0, 0),  # tzinfo=None
        )
