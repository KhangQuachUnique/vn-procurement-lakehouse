from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.tbmt_api import (
    TbmtApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.tbmt_source import (
    IncompleteIngestionError,
    TbmtSource,
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
def tbmt_window() -> IngestionWindow:
    return IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )


def test_tbmt_source_conforms_to_source_port() -> None:
    api = MagicMock(spec=TbmtApi)
    source = TbmtSource(api=api)
    source_port: SourcePort = source
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


def test_tbmt_source_invalid_page_size() -> None:
    api = MagicMock(spec=TbmtApi)
    with pytest.raises(ValueError, match="page_size must be positive"):
        TbmtSource(api=api, page_size=0)
    with pytest.raises(ValueError, match="page_size must be positive"):
        TbmtSource(api=api, page_size=-1)


def test_tbmt_source_rejects_unsupported_resource_eagerly() -> None:
    api = MagicMock(spec=TbmtApi)
    source = TbmtSource(api=api)
    bad_window = IngestionWindow(
        resource="project",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )
    with pytest.raises(ValueError, match="Unsupported resource: project"):
        source.fetch(bad_window)
    api.search.assert_not_called()


def test_tbmt_source_empty_window(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
    )

    source = TbmtSource(api=api, page_size=50)
    records = list(source.fetch(tbmt_window))
    assert records == []


def test_tbmt_source_single_page_success(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [
            {"id": "TBMT001", "bidName": "Notice 1", "bidForm": "DTRR", "processApply": "LDT"},
            {"id": "TBMT002", "bidName": "Notice 2", "bidForm": "CGTTRG", "processApply": "LDT"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_notice_detail.side_effect = lambda item: {
        "id": item["id"],
        "title": item["bidName"],
    }

    source = TbmtSource(api=api, page_size=50)
    records = list(source.fetch(tbmt_window))

    assert len(records) == 2
    assert records[0]["id"] == "TBMT001"
    assert records[0]["searchMetadata"]["bidName"] == "Notice 1"
    assert records[1]["id"] == "TBMT002"
    assert records[1]["searchMetadata"]["bidName"] == "Notice 2"


def test_tbmt_source_multi_page_success(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.side_effect = [
        make_search_page(
            [
                {"id": "TBMT001", "bidName": "Notice 1"},
                {"id": "TBMT002", "bidName": "Notice 2"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=0,
            page_size=2,
            last=False,
        ),
        make_search_page(
            [
                {"id": "TBMT003", "bidName": "Notice 3"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=1,
            page_size=2,
            first=False,
            last=True,
        ),
    ]
    api.get_notice_detail.side_effect = lambda item: {"id": item["id"]}

    source = TbmtSource(api=api, page_size=2)
    records = list(source.fetch(tbmt_window))

    assert len(records) == 3
    assert [r["id"] for r in records] == ["TBMT001", "TBMT002", "TBMT003"]
    assert api.search.call_count == 2


def test_tbmt_api_routes_reoffer_and_vk_adb() -> None:
    client = MagicMock()
    client.post.return_value = {"status": "ok"}
    api = TbmtApi(client)

    # Reoffer by bidForm
    api.get_notice_detail({"id": "N1", "bidForm": "CGTTRG"})
    client.post.assert_called_with(
        "/o/egp-portal-contractor-selection-v2/services/online-reoffer/detail",
        {"id": "N1"},
    )

    # Reoffer by stepCode
    client.reset_mock()
    api.get_notice_detail({"id": "N2", "stepCode": "reoffer-price-step-1"})
    client.post.assert_called_with(
        "/o/egp-portal-contractor-selection-v2/services/online-reoffer/detail",
        {"id": "N2"},
    )

    # VK ADB by processApply
    client.reset_mock()
    api.get_notice_detail({"id": "N3", "processApply": "WB"})
    client.post.assert_called_with(
        "/o/egp-portal-contractor-selection-v2/services/lcnt_tbmt_ttc_vk_adb",
        {"id": "N3"},
    )

    # Standard fallback
    client.reset_mock()
    api.get_notice_detail({"id": "N4", "processApply": "LDT"})
    client.post.assert_called_with(
        "/o/egp-portal-contractor-selection-v2/services/lcnt_tbmt_ttc_ldt",
        {"id": "N4"},
    )


def test_tbmt_source_raises_on_duplicate_id(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [
            {"id": "TBMT001"},
            {"id": "TBMT001"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_notice_detail.return_value = {"id": "TBMT001"}

    source = TbmtSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Duplicate notice id: TBMT001"):
        list(source.fetch(tbmt_window))


def test_tbmt_source_raises_on_invalid_id(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [{"id": ""}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )

    source = TbmtSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="TBMT search item missing valid id"):
        list(source.fetch(tbmt_window))


def test_tbmt_source_raises_on_count_mismatch(tbmt_window: IngestionWindow) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [{"id": "TBMT001"}],
        total_elements=5,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_notice_detail.return_value = {"id": "TBMT001"}

    source = TbmtSource(api=api, page_size=50)
    with pytest.raises(
        IncompleteIngestionError, match="Incomplete ingestion: expected 5, received 1"
    ):
        list(source.fetch(tbmt_window))


def test_tbmt_source_empty_detail_falls_back_to_search_metadata(
    tbmt_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [{"id": "TBMT001", "bidName": "Notice Test"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_notice_detail.return_value = {}

    source = TbmtSource(api=api, page_size=50)
    records = list(source.fetch(tbmt_window))

    assert len(records) == 1
    assert records[0]["id"] == "TBMT001"
    assert records[0]["_detail_status"] == "EMPTY"
    assert records[0]["_search_metadata"]["bidName"] == "Notice Test"
    assert records[0]["searchMetadata"]["bidName"] == "Notice Test"


def test_tbmt_source_error_detail_falls_back_to_search_metadata(
    tbmt_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=TbmtApi)
    api.search.return_value = make_search_page(
        [{"id": "TBMT001", "bidName": "Notice Error"}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_notice_detail.side_effect = RuntimeError("Detail fetch timeout")

    source = TbmtSource(api=api, page_size=50)
    records = list(source.fetch(tbmt_window))

    assert len(records) == 1
    assert records[0]["id"] == "TBMT001"
    assert records[0]["_detail_status"] == "ERROR"
    assert "RuntimeError: Detail fetch timeout" in records[0]["_detail_note"]
    assert records[0]["_search_metadata"]["bidName"] == "Notice Error"
