from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.khlcnt_api import (
    KhlcntApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.khlcnt_source import (
    IncompleteIngestionError,
    KhlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
)
from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def make_search_page(
    content: list[dict[str, Any]],
    total_elements: int,
    total_pages: int,
    current_page: int,
    page_size: int = 50,
    first: bool = True,
    last: bool = True,
) -> SearchPage:
    return SearchPage.model_validate(
        {
            "content": content,
            "totalElements": total_elements,
            "totalPages": total_pages,
            "currentPage": current_page,
            "pageSize": page_size,
            "first": first,
            "last": last,
        }
    )


@pytest.fixture
def khlcnt_window() -> IngestionWindow:
    return IngestionWindow(
        resource="khlcnt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )


@pytest.fixture
def mock_api() -> MagicMock:
    return MagicMock(spec=KhlcntApi)


# --- Initialization Tests ---


def test_init_invalid_page_size_raises(mock_api: MagicMock) -> None:
    with pytest.raises(ValueError, match="page_size must be positive"):
        KhlcntSource(mock_api, page_size=0)


def test_conforms_to_source_port(mock_api: MagicMock) -> None:
    source = KhlcntSource(mock_api)
    source_port: SourcePort = source
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


# --- Resource Validation Tests ---


def test_fetch_unsupported_resource_raises_eagerly(mock_api: MagicMock) -> None:
    source = KhlcntSource(mock_api)
    window = IngestionWindow(
        resource="project",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Unsupported resource: project"):
        source.fetch(window)


# --- Empty Window Tests ---


def test_fetch_empty_window_yields_nothing(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
        first=True,
        last=False,
    )

    source = KhlcntSource(mock_api)
    records = list(source.fetch(khlcnt_window))

    assert records == []
    mock_api.search.assert_called_once()
    mock_api.get_plan_detail.assert_not_called()


# --- Happy Path & Package Enrichment Tests ---


def test_fetch_single_page_enriches_packages(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.return_value = {
        "id": "PLAN001",
        "planNo": "PL123",
        "bidpPlanDetailToProjectList": [
            {"id": "PKG001", "name": "Gói thầu 1"},
            {"id": "PKG002", "name": "Gói thầu 2"},
        ],
    }
    mock_api.get_bid_package_detail.side_effect = [
        {"id": "PKG001", "bidPrice": 1000},
        {"id": "PKG002", "bidPrice": 2000},
    ]

    source = KhlcntSource(mock_api)
    records = list(source.fetch(khlcnt_window))

    assert len(records) == 1
    record = records[0]
    assert record["id"] == "PLAN001"
    packages = record["bidpPlanDetailToProjectList"]
    assert len(packages) == 2
    assert packages[0]["detail"]["bidPrice"] == 1000
    assert packages[1]["detail"]["bidPrice"] == 2000
    assert mock_api.get_bid_package_detail.call_count == 2


def test_fetch_multi_page_with_last_false_succeeds(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    page_0 = make_search_page(
        content=[{"id": "PLAN001"}],
        total_elements=2,
        total_pages=2,
        current_page=0,
        page_size=1,
        first=True,
        last=False,
    )
    page_1 = make_search_page(
        content=[{"id": "PLAN002"}],
        total_elements=2,
        total_pages=2,
        current_page=1,
        page_size=1,
        first=False,
        last=False,  # Muasamcong returns last=False on the real final data page
    )
    mock_api.search.side_effect = [page_0, page_1]
    mock_api.get_plan_detail.side_effect = [
        {"id": "PLAN001"},
        {"id": "PLAN002"},
    ]

    source = KhlcntSource(mock_api, page_size=1)
    records = list(source.fetch(khlcnt_window))

    assert len(records) == 2
    assert records[0]["id"] == "PLAN001"
    assert records[1]["id"] == "PLAN002"
    assert mock_api.search.call_count == 2


# --- Incomplete & Corrupted Metadata Tests ---


def test_fetch_missing_plan_id_raises(mock_api: MagicMock, khlcnt_window: IngestionWindow) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"name": "No ID"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )

    source = KhlcntSource(mock_api)
    with pytest.raises(IncompleteIngestionError, match="missing valid id"):
        list(source.fetch(khlcnt_window))


def test_fetch_duplicate_plan_id_raises(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001"}, {"id": "PLAN001"}],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.return_value = {"id": "PLAN001"}

    source = KhlcntSource(mock_api)
    with pytest.raises(IncompleteIngestionError, match="Duplicate plan id"):
        list(source.fetch(khlcnt_window))


def test_fetch_invalid_plan_detail_falls_back_to_search_item(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001", "name": "Plan Alpha"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.return_value = {}  # Empty/invalid dict

    source = KhlcntSource(mock_api)
    records = list(source.fetch(khlcnt_window))

    assert len(records) == 1
    assert records[0]["id"] == "PLAN001"
    assert records[0]["_detail_status"] == "EMPTY"
    assert records[0]["_search_metadata"]["name"] == "Plan Alpha"
    assert records[0]["searchMetadata"]["name"] == "Plan Alpha"


def test_fetch_plan_detail_exception_raises(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001", "name": "Plan Beta"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.side_effect = RuntimeError("API down")

    source = KhlcntSource(mock_api)
    with pytest.raises(RuntimeError, match="API down"):
        list(source.fetch(khlcnt_window))


def test_fetch_incomplete_ingestion_count_mismatch_raises(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001"}],
        total_elements=2,  # Server expected 2, but only 1 on final page
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.return_value = {"id": "PLAN001"}

    source = KhlcntSource(mock_api)
    with pytest.raises(
        IncompleteIngestionError, match="Incomplete ingestion: expected 2, received 1"
    ):
        list(source.fetch(khlcnt_window))


def test_khlcnt_source_integration_with_ingest_daily_window(
    mock_api: MagicMock, khlcnt_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PLAN001"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    mock_api.get_plan_detail.return_value = {"id": "PLAN001", "name": "Plan 1"}

    source = KhlcntSource(mock_api)
    writer = MagicMock()
    repository = MagicMock()

    batch_run_id = uuid4()
    mock_batch = PublishedBatch(
        run_id=batch_run_id,
        record_count=1,
        storage_uri="mock://bronze/khlcnt/run1",
    )
    writer.write.return_value = mock_batch

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    batch = service.execute(khlcnt_window)
    assert batch == mock_batch
    assert batch.record_count == 1
    repository.create.assert_called_once()
    assert repository.update.call_count == 2
    writer.write.assert_called_once()
