from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.bid_opening_api import (
    BidOpeningApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.bid_opening_source import (
    BidOpeningSource,
    IncompleteIngestionError,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
)
from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow


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
def bid_opening_window() -> IngestionWindow:
    return IngestionWindow(
        resource="bid_opening",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )


def test_bid_opening_source_conforms_to_source_port() -> None:
    api = MagicMock(spec=BidOpeningApi)
    source = BidOpeningSource(api=api)
    source_port: SourcePort = source
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


def test_bid_opening_source_invalid_page_size() -> None:
    api = MagicMock(spec=BidOpeningApi)
    with pytest.raises(ValueError, match="page_size must be positive"):
        BidOpeningSource(api=api, page_size=0)
    with pytest.raises(ValueError, match="page_size must be positive"):
        BidOpeningSource(api=api, page_size=-1)


def test_bid_opening_source_rejects_unsupported_resource_eagerly() -> None:
    api = MagicMock(spec=BidOpeningApi)
    source = BidOpeningSource(api=api)
    bad_window = IngestionWindow(
        resource="project",
        start_date=date(2026, 10, 10),
        end_date_exclusive=date(2026, 10, 11),
    )
    with pytest.raises(ValueError, match="Unsupported resource: project"):
        source.fetch(bad_window)
    api.search.assert_not_called()


def test_bid_opening_source_empty_window(bid_opening_window: IngestionWindow) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.return_value = make_search_page(
        [],
        total_elements=0,
        total_pages=0,
        current_page=0,
        page_size=50,
    )

    source = BidOpeningSource(api=api, page_size=50)
    records = list(source.fetch(bid_opening_window))
    assert records == []


def test_bid_opening_source_single_page_success(
    bid_opening_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.return_value = make_search_page(
        [
            {"notifyId": "OPEN001", "notifyNo": "IB001"},
            {"id": "OPEN002", "notifyNo": "IB002"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_bid_opening_detail.side_effect = lambda item: {
        "id": item.get("notifyId") or item.get("id"),
        "notify": {"ok": True},
    }

    source = BidOpeningSource(api=api, page_size=50)
    records = list(source.fetch(bid_opening_window))

    assert len(records) == 2
    assert records[0]["id"] == "OPEN001"
    assert records[0]["searchMetadata"]["notifyNo"] == "IB001"
    assert records[1]["id"] == "OPEN002"
    assert records[1]["searchMetadata"]["notifyNo"] == "IB002"
    assert api.get_bid_opening_detail.call_count == 2


def test_bid_opening_source_multi_page_success(
    bid_opening_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.side_effect = [
        make_search_page(
            [
                {"notifyId": "OPEN001"},
                {"notifyId": "OPEN002"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=0,
            page_size=2,
            last=False,
        ),
        make_search_page(
            [
                {"notifyId": "OPEN003"},
            ],
            total_elements=3,
            total_pages=2,
            current_page=1,
            page_size=2,
            first=False,
            last=True,
        ),
    ]
    api.get_bid_opening_detail.side_effect = lambda item: {"id": item["notifyId"]}

    source = BidOpeningSource(api=api, page_size=2)
    records = list(source.fetch(bid_opening_window))

    assert len(records) == 3
    assert [r["id"] for r in records] == ["OPEN001", "OPEN002", "OPEN003"]
    assert api.search.call_count == 2


def test_bid_opening_api_single_stage() -> None:
    client = MagicMock()
    client.post.side_effect = [
        {"notify_data": 1},  # notify
        {"roundmng_data": 1, "bidoBidroundMngViewDTO": {"bidMode": "1_MTHS"}},  # roundmng
        {"bid_open_data": 1},  # bid_open
    ]
    client.post_array.return_value = [{"lot": 1}]

    api = BidOpeningApi(client)
    item = {"notifyId": "N1", "notifyNo": "NO1", "bidMode": "1_MTHS"}
    res = api.get_bid_opening_detail(item)

    assert "notify" in res
    assert "roundmng" in res
    assert "bid_open" in res
    assert "lot_open_detail" in res
    assert res["lot_open_detail"] == [{"lot": 1}]
    assert client.post.call_count == 3
    assert client.post_array.call_count == 1


def test_bid_opening_api_dual_stage_with_financial() -> None:
    client = MagicMock()
    client.post.side_effect = [
        {"notify_data": 1},  # notify
        {
            "roundmng_data": 1,
            "bidoBidroundMngViewDTO": {
                "bidMode": "1_HTHS",
                "successBidOpenDateTc": "2026-10-10T10:00:00.000Z",
            },
        },  # roundmng
        {"bid_open_tech": 1},  # bid_open technical
        {"bid_open_fin": 1},  # bid_open financial
    ]
    client.post_array.side_effect = [
        [{"lot_tech": 1}],
        [{"lot_fin": 1}],
    ]

    api = BidOpeningApi(client)
    item = {"notifyId": "N1", "notifyNo": "NO1", "bidMode": "1_HTHS"}
    res = api.get_bid_opening_detail(item)

    assert "bid_open_technical" in res
    assert "lot_open_detail_technical" in res
    assert "bid_open_financial" in res
    assert "lot_open_detail_financial" in res
    assert client.post.call_count == 4
    assert client.post_array.call_count == 2


def test_bid_opening_source_raises_on_duplicate_id(
    bid_opening_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.return_value = make_search_page(
        [
            {"notifyId": "OPEN001"},
            {"notifyId": "OPEN001"},
        ],
        total_elements=2,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_bid_opening_detail.return_value = {"id": "OPEN001"}

    source = BidOpeningSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Duplicate bid opening id: OPEN001"):
        list(source.fetch(bid_opening_window))


def test_bid_opening_source_raises_on_invalid_id(
    bid_opening_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.return_value = make_search_page(
        [{"notifyId": ""}],
        total_elements=1,
        total_pages=1,
        current_page=0,
        page_size=50,
    )

    source = BidOpeningSource(api=api, page_size=50)
    with pytest.raises(IncompleteIngestionError, match="Bid opening search item missing valid id"):
        list(source.fetch(bid_opening_window))


def test_bid_opening_source_raises_on_count_mismatch(
    bid_opening_window: IngestionWindow,
) -> None:
    api = MagicMock(spec=BidOpeningApi)
    api.search.return_value = make_search_page(
        [{"notifyId": "OPEN001"}],
        total_elements=5,
        total_pages=1,
        current_page=0,
        page_size=50,
    )
    api.get_bid_opening_detail.return_value = {"id": "OPEN001"}

    source = BidOpeningSource(api=api, page_size=50)
    with pytest.raises(
        IncompleteIngestionError, match="Incomplete ingestion: expected 5, received 1"
    ):
        list(source.fetch(bid_opening_window))
