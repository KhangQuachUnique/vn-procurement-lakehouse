from datetime import date

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.fake_source import FakeTenderSource
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow


def test_fake_tender_source_yields_tbmt() -> None:
    source = FakeTenderSource()
    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    records = list(source.fetch(window))
    assert len(records) == 2
    assert records[0]["notifyNo"] == "IB001"
    assert records[1]["notifyNo"] == "IB002"


def test_fake_tender_source_unsupported_resource_raises() -> None:
    source = FakeTenderSource()
    window = IngestionWindow(
        resource="unsupported",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Unsupported resource: unsupported"):
        list(source.fetch(window))
