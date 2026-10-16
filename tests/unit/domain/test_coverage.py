from datetime import date
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.domain.coverage import DayCoverage


def test_day_coverage_creation() -> None:
    run_id = uuid4()
    coverage = DayCoverage(
        date=date(2026, 6, 1),
        status="VERIFIED",
        record_count=100,
        run_id=run_id,
        storage_uri="mock/path",
    )
    assert coverage.date == date(2026, 6, 1)
    assert coverage.status == "VERIFIED"
    assert coverage.record_count == 100
    assert coverage.run_id == run_id
    assert coverage.storage_uri == "mock/path"


def test_day_coverage_frozen() -> None:
    coverage = DayCoverage(
        date=date(2026, 6, 1),
        status="VERIFIED",
        record_count=100,
        run_id=None,
        storage_uri=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        coverage.status = "FAILED"  # type: ignore[misc]
