from datetime import date
from uuid import UUID, uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.application.ports import RawPayload
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun


@pytest.fixture
def sample_window() -> IngestionWindow:
    return IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )


@pytest.fixture
def sample_records() -> list[RawPayload]:
    return [
        {"id": "IB001", "name": "Goi thau 1", "amount": 1000},
        {"id": "IB002", "name": "Goi thau 2", "amount": 2000},
    ]


@pytest.fixture
def sample_run_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_run(sample_run_id: UUID, sample_window: IngestionWindow) -> IngestionRun:
    return IngestionRun(
        run_id=sample_run_id,
        window=sample_window,
    )
