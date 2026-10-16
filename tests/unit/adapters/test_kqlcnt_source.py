from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.kqlcnt_api import (
    KqlcntApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.kqlcnt_source import (
    IncompleteIngestionError,
    KqlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
)
from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def make_search_page(
    content: list[dict[str, Any]],
    *,
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
def kqlcnt_window() -> IngestionWindow:
    return IngestionWindow(
        resource="kqlcnt",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )


def test_kqlcnt_source_conforms_to_source_port() -> None:
    api = MagicMock(spec=KqlcntApi)
    source = KqlcntSource(api=api)
    source_port: SourcePort = source
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


def test_kqlcnt_source_invalid_page_size() -> None:
    api = MagicMock(spec=KqlcntApi)
    with pytest.raises(ValueError, match="page_size must be positive"):
        KqlcntSource(api=api, page_size=0)
    with pytest.raises(ValueError, match="page_size must be positive"):
        KqlcntSource(api=api, page_size=-1)


def test_kqlcnt_source_rejects_unsupported_resource_eagerly() -> None:
    api = MagicMock(spec=KqlcntApi)
    source = KqlcntSource(api=api)
    bad_window = IngestionWindow(
        resource="project",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )
    with pytest.raises(ValueError, match="Unsupported resource: project"):
        source.fetch(bad_window)
    api.search.assert_not_called()


def test_kqlcnt_source_empty_window(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.return_value = make_search_page(
        [],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
    )

    source = KqlcntSource(api=api, page_size=50)
    records = list(source.fetch(kqlcnt_window))
    assert records == []


def test_kqlcnt_source_single_page_success(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.return_value = make_search_page(
        [
            {"inputResultId": "RES001", "notifyNo": "IB001"},
            {"id": "RES002", "notifyNo": "IB002"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_result_detail.side_effect = lambda result_id: {
        "bideContractorInputResultDTO": {"id": result_id},
    }

    source = KqlcntSource(api=api, page_size=50)
    records = list(source.fetch(kqlcnt_window))

    assert len(records) == 2
    assert records[0]["bideContractorInputResultDTO"]["id"] == "RES001"
    assert records[0]["searchMetadata"]["notifyNo"] == "IB001"
    assert records[1]["bideContractorInputResultDTO"]["id"] == "RES002"
    assert records[1]["searchMetadata"]["notifyNo"] == "IB002"
    assert api.get_result_detail.call_count == 2


def test_kqlcnt_source_multi_page_success(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.side_effect = [
        make_search_page(
            [
                {"inputResultId": "RES001"},
                {"inputResultId": "RES002"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=0,
            page_size=2,
            last=False,
        ),
        make_search_page(
            [
                {"inputResultId": "RES003"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=1,
            page_size=2,
            first=False,
            last=True,
        ),
    ]
    api.get_result_detail.side_effect = lambda result_id: {"id": result_id}

    source = KqlcntSource(api=api, page_size=2)
    records = list(source.fetch(kqlcnt_window))

    assert len(records) == 3
    assert [r["id"] for r in records] == ["RES001", "RES002", "RES003"]
    assert api.search.call_count == 2


def test_kqlcnt_source_raises_on_duplicate_id(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.return_value = make_search_page(
        [
            {"inputResultId": "RES001"},
            {"inputResultId": "RES001"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_result_detail.return_value = {"id": "RES001"}

    source = KqlcntSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Duplicate KQLCNT id: RES001"):
        list(source.fetch(kqlcnt_window))


def test_kqlcnt_source_raises_on_invalid_id(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.return_value = make_search_page(
        [{"inputResultId": ""}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )

    source = KqlcntSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="KQLCNT search item missing valid id"):
        list(source.fetch(kqlcnt_window))


def test_kqlcnt_source_raises_on_count_mismatch(kqlcnt_window: IngestionWindow) -> None:
    api = MagicMock(spec=KqlcntApi)
    api.search.return_value = make_search_page(
        [{"inputResultId": "RES001"}],
        total_elements=5,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_result_detail.return_value = {"id": "RES001"}

    source = KqlcntSource(api=api, page_size=50)
    with pytest.raises(
        IncompleteIngestionError, match="Incomplete ingestion: expected 5, received 1"
    ):
        list(source.fetch(kqlcnt_window))
