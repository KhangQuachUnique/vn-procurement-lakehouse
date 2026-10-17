from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.project_api import (
    ProjectApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.project_source import (
    IncompleteIngestionError,
    ProjectSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import SearchPage
from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def make_search_page(
    content: list[dict[str, Any]],
    *,
    total_elements: int,
    total_pages: int,
    current_page: int = 0,
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
def project_window() -> IngestionWindow:
    return IngestionWindow(
        resource="project",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )


@pytest.fixture
def mock_api() -> MagicMock:
    return MagicMock(spec=ProjectApi)


# --- Initialization & Configuration Tests ---


@pytest.mark.parametrize("invalid_page_size", [0, -1, -50])
def test_init_invalid_page_size_raises(mock_api: MagicMock, invalid_page_size: int) -> None:
    with pytest.raises(ValueError, match="page_size must be positive"):
        ProjectSource(mock_api, page_size=invalid_page_size)


def test_init_valid_default_page_size(mock_api: MagicMock) -> None:
    source = ProjectSource(mock_api)
    assert source._page_size == 50


# --- Resource Validation Tests ---


def test_fetch_unsupported_resource_raises(mock_api: MagicMock) -> None:
    source = ProjectSource(mock_api)
    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Unsupported resource: tbmt"):
        list(source.fetch(window))


def test_fetch_unsupported_resource_raises_eagerly_without_iteration(mock_api: MagicMock) -> None:
    source = ProjectSource(mock_api)
    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Unsupported resource: tbmt"):
        # Eager validation: fails immediately when fetch() is called, before iteration
        source.fetch(window)


# --- Empty Window Tests ---


def test_fetch_empty_window_yields_no_records(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )

    source = ProjectSource(mock_api, page_size=50)
    records = list(source.fetch(project_window))

    assert records == []
    mock_api.search.assert_called_once_with(
        page_number=0,
        page_size=50,
        window_from="2026-06-19",
        window_to="2026-06-20",
    )
    mock_api.get_project_detail.assert_not_called()


def test_fetch_empty_window_with_last_false_yields_nothing(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    # Muasamcong may return last=False even for empty windows
    mock_api.search.return_value = make_search_page(
        content=[],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
        first=True,
        last=False,
    )

    source = ProjectSource(mock_api, page_size=50)
    records = list(source.fetch(project_window))

    assert records == []
    mock_api.search.assert_called_once()
    mock_api.get_project_detail.assert_not_called()


def test_fetch_empty_total_with_content_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )

    source = ProjectSource(mock_api)
    with pytest.raises(IncompleteIngestionError, match="Invalid empty search result"):
        list(source.fetch(project_window))


# --- Happy Path Tests (Single & Multi-Page) ---


def test_fetch_single_page_success(mock_api: MagicMock, project_window: IngestionWindow) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ002"}],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.side_effect = [
        {"id": "PRJ001", "name": "Dự án Nâng cấp Đường A"},
        {"id": "PRJ002", "name": "Dự án Xây dựng Trường B"},
    ]

    source = ProjectSource(mock_api, page_size=50)
    records = list(source.fetch(project_window))

    assert len(records) == 2
    assert records[0]["id"] == "PRJ001"
    assert records[0]["name"] == "Dự án Nâng cấp Đường A"
    assert records[0]["_detail_status"] == "SUCCESS"
    assert records[0]["_search_metadata"] == {"id": "PRJ001"}
    assert records[1]["id"] == "PRJ002"
    assert records[1]["name"] == "Dự án Xây dựng Trường B"
    assert records[1]["_detail_status"] == "SUCCESS"

    mock_api.search.assert_called_once_with(
        page_number=0,
        page_size=50,
        window_from="2026-06-19",
        window_to="2026-06-20",
    )
    assert mock_api.get_project_detail.call_count == 2
    mock_api.get_project_detail.assert_any_call("PRJ001")
    mock_api.get_project_detail.assert_any_call("PRJ002")


def test_fetch_multi_page_success(mock_api: MagicMock, project_window: IngestionWindow) -> None:
    page_0 = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ002"}],
        total_elements=3,
        total_pages=2,
        current_page=0,
        page_size=2,
        first=True,
        last=False,
    )
    page_1 = make_search_page(
        content=[{"id": "PRJ003"}],
        total_elements=3,
        total_pages=2,
        current_page=1,
        page_size=2,
        first=False,
        last=True,
    )
    mock_api.search.side_effect = [page_0, page_1]
    mock_api.get_project_detail.side_effect = [
        {"id": "PRJ001", "name": "Project 1"},
        {"id": "PRJ002", "name": "Project 2"},
        {"id": "PRJ003", "name": "Project 3"},
    ]

    source = ProjectSource(mock_api, page_size=2)
    records = list(source.fetch(project_window))

    assert len(records) == 3
    assert [r["id"] for r in records] == ["PRJ001", "PRJ002", "PRJ003"]
    assert mock_api.search.call_count == 2
    mock_api.search.assert_any_call(
        page_number=0,
        page_size=2,
        window_from="2026-06-19",
        window_to="2026-06-20",
    )
    mock_api.search.assert_any_call(
        page_number=1,
        page_size=2,
        window_from="2026-06-19",
        window_to="2026-06-20",
    )


# --- Pagination Metadata Validation Tests ---


def test_fetch_page_number_mismatch_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=1,
        total_pages=1,
        current_page=5,  # Mismatch: expected 0
        page_size=50,
        first=False,
        last=True,
    )

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Expected page 0, received 5"):
        list(source.fetch(project_window))


def test_fetch_page_size_mismatch_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=20,  # Mismatch: source configured with 50
        first=True,
        last=True,
    )

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Unexpected page size"):
        list(source.fetch(project_window))


def test_fetch_pagination_total_elements_changed_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    page_0 = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=2,
        total_pages=2,
        current_page=0,
        page_size=1,
        first=True,
        last=False,
    )
    page_1 = make_search_page(
        content=[{"id": "PRJ002"}],
        total_elements=3,  # Total elements drifted from 2 to 3
        total_pages=2,
        current_page=1,
        page_size=1,
        first=False,
        last=True,
    )
    mock_api.search.side_effect = [page_0, page_1]
    mock_api.get_project_detail.return_value = {"id": "PRJ001"}

    source = ProjectSource(mock_api, page_size=1)
    with pytest.raises(
        IncompleteIngestionError, match="Pagination metadata changed during ingestion"
    ):
        list(source.fetch(project_window))


def test_fetch_pagination_total_pages_changed_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    page_0 = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=2,
        total_pages=2,
        current_page=0,
        page_size=1,
        first=True,
        last=False,
    )
    page_1 = make_search_page(
        content=[{"id": "PRJ002"}],
        total_elements=2,
        total_pages=3,  # Total pages drifted from 2 to 3
        current_page=1,
        page_size=1,
        first=False,
        last=False,
    )
    mock_api.search.side_effect = [page_0, page_1]
    mock_api.get_project_detail.return_value = {"id": "PRJ001"}

    source = ProjectSource(mock_api, page_size=1)
    with pytest.raises(
        IncompleteIngestionError, match="Pagination metadata changed during ingestion"
    ):
        list(source.fetch(project_window))


# --- Boundary & Last-Page Consistency Tests ---


def test_fetch_unexpected_end_empty_content_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    # total_elements > 0 but content is empty
    mock_api.search.return_value = make_search_page(
        content=[],
        total_elements=10,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Pagination ended unexpectedly"):
        list(source.fetch(project_window))


def test_fetch_expected_pages_zero_with_non_zero_elements_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=1,
        total_pages=0,  # 0 pages despite 1 element
        current_page=0,
        page_size=50,
        first=True,
        last=False,
    )

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Pagination ended unexpectedly"):
        list(source.fetch(project_window))


def test_fetch_final_page_with_last_false_succeeds(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    # Muasamcong returns last=False on the actual final page of data (totalPages - 1)
    page_0 = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=2,
        total_pages=2,
        current_page=0,
        page_size=1,
        first=True,
        last=False,
    )
    page_1 = make_search_page(
        content=[{"id": "PRJ002"}],
        total_elements=2,
        total_pages=2,
        current_page=1,
        page_size=1,
        first=False,
        last=False,  # Unreliable API behavior: last is False on the final data page
    )
    mock_api.search.side_effect = [page_0, page_1]
    mock_api.get_project_detail.side_effect = [
        {"id": "PRJ001", "name": "Project 1"},
        {"id": "PRJ002", "name": "Project 2"},
    ]

    source = ProjectSource(mock_api, page_size=1)
    records = list(source.fetch(project_window))

    assert len(records) == 2
    assert records[0]["id"] == "PRJ001"
    assert records[1]["id"] == "PRJ002"
    assert mock_api.search.call_count == 2
    assert mock_api.get_project_detail.call_count == 2


def test_fetch_content_exceeds_configured_page_size_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    # Page size is 1, but content returns 2 items
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ002"}],
        total_elements=2,
        total_pages=2,
        current_page=0,
        page_size=1,
        first=True,
        last=False,
    )

    source = ProjectSource(mock_api, page_size=1)
    with pytest.raises(IncompleteIngestionError, match="Page exceeds configured size"):
        list(source.fetch(project_window))


# --- Record Detail & ID Validation Tests ---


@pytest.mark.parametrize(
    "invalid_item",
    [
        {},
        {"id": None},
        {"id": ""},
        {"id": "   "},
        {"id": 12345},
    ],
)
def test_fetch_missing_or_invalid_project_id_raises(
    mock_api: MagicMock, project_window: IngestionWindow, invalid_item: dict[str, Any]
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[invalid_item],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Project search item missing valid id"):
        list(source.fetch(project_window))


def test_fetch_duplicate_project_id_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ001"}],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.return_value = {"id": "PRJ001"}

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Duplicate project id: PRJ001"):
        list(source.fetch(project_window))


@pytest.mark.parametrize("invalid_detail", [None, {}, "string", [1, 2]])
def test_fetch_invalid_project_detail_falls_back_to_search_item(
    mock_api: MagicMock, project_window: IngestionWindow, invalid_detail: Any
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001", "name": "Project Alpha"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.return_value = invalid_detail

    source = ProjectSource(mock_api, page_size=50)
    records = list(source.fetch(project_window))

    assert len(records) == 1
    assert records[0]["id"] == "PRJ001"
    assert records[0]["_detail_status"] == "EMPTY"
    assert records[0]["_search_metadata"]["name"] == "Project Alpha"
    assert records[0]["searchMetadata"]["name"] == "Project Alpha"


def test_fetch_project_detail_exception_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001", "name": "Project Beta"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.side_effect = RuntimeError("Connection timeout")

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(RuntimeError, match="Connection timeout"):
        list(source.fetch(project_window))


# --- Total Records Count Validation Tests ---


def test_fetch_received_more_records_than_expected_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ002"}],
        total_elements=1,  # expected 1, but 2 returned
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.side_effect = [
        {"id": "PRJ001"},
        {"id": "PRJ002"},
    ]

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Received more records than expected"):
        list(source.fetch(project_window))


def test_fetch_fewer_records_on_last_page_raises(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    # Expected 3 elements, but only 2 returned before last=True
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}, {"id": "PRJ002"}],
        total_elements=3,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.side_effect = [
        {"id": "PRJ001"},
        {"id": "PRJ002"},
    ]

    source = ProjectSource(mock_api, page_size=50)
    with pytest.raises(
        IncompleteIngestionError, match="Incomplete ingestion: expected 3, received 2"
    ):
        list(source.fetch(project_window))


# --- Port Protocol & Bootstrap Service Compatibility Tests ---


def test_project_source_conforms_to_source_port(mock_api: MagicMock) -> None:
    source = ProjectSource(mock_api)
    source_port: SourcePort = source
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


def test_project_source_integration_with_ingest_daily_window(
    mock_api: MagicMock, project_window: IngestionWindow
) -> None:
    mock_api.search.return_value = make_search_page(
        content=[{"id": "PRJ001"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
        first=True,
        last=True,
    )
    mock_api.get_project_detail.return_value = {
        "id": "PRJ001",
        "name": "Dự án Nâng cấp Đường A",
    }

    source = ProjectSource(mock_api, page_size=50)
    writer = MagicMock()
    repository = MagicMock()

    batch_run_id = uuid4()
    mock_batch = PublishedBatch(
        run_id=batch_run_id,
        record_count=1,
        storage_uri="mock://bronze/project/run1",
    )
    writer.write.return_value = mock_batch

    service = IngestDailyWindow(
        source=source,
        writer=writer,
        run_repository=repository,
    )

    batch = service.execute(project_window)

    assert batch == mock_batch
    assert batch.record_count == 1
    repository.create.assert_called_once()
    assert repository.update.call_count == 2
    writer.write.assert_called_once()
