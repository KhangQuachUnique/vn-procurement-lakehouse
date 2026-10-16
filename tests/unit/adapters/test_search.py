import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.search import (
    build_bid_opening_search_payload,
    build_khlcnt_search_payload,
    build_kqlcnt_search_payload,
    build_project_search_payload,
    build_search_payload,
    build_tbmt_search_payload,
)


def test_build_project_search_payload_structure() -> None:
    payload = build_project_search_payload(
        page_number=0,
        page_size=50,
        window_from="2026-10-16",
        window_to="2026-10-17",
    )

    assert len(payload) == 1
    query_obj = payload[0]
    assert query_obj["pageSize"] == 50
    assert query_obj["pageNumber"] == 0

    queries = query_obj["query"]
    assert len(queries) == 1
    query = queries[0]
    assert query["index"] == "es-contractor-selection"
    assert query["matchType"] == "all-1"
    assert query["matchFields"] == ["notifyNo", "bidName"]

    filters = query["filters"]
    assert len(filters) == 2
    assert filters[0] == {
        "fieldName": "publicDate",
        "searchType": "range",
        "from": "2026-10-16",
        "to": "2026-10-17",
    }
    assert filters[1] == {
        "fieldName": "type",
        "searchType": "in",
        "fieldValues": ["es-bidp-project-p"],
    }


def test_build_khlcnt_search_payload_structure() -> None:
    payload = build_khlcnt_search_payload(
        page_number=1,
        page_size=25,
        window_from="2026-10-16",
        window_to="2026-10-17",
    )

    query = payload[0]["query"][0]
    assert query["index"] == "es-contractor-selection"
    filters = query["filters"]
    assert len(filters) == 2
    assert filters[0] == {
        "fieldName": "publicDate",
        "searchType": "range",
        "from": "2026-10-16",
        "to": "2026-10-17",
    }
    assert filters[1] == {
        "fieldName": "type",
        "searchType": "in",
        "fieldValues": ["es-plan-project-p"],
    }


def test_build_tbmt_search_payload_structure() -> None:
    payload = build_tbmt_search_payload(
        page_number=0,
        page_size=50,
        window_from="2026-10-16",
        window_to="2026-10-17",
    )

    query = payload[0]["query"][0]
    assert query["index"] == "es-contractor-selection"
    filters = query["filters"]
    assert len(filters) == 3
    assert filters[0] == {
        "fieldName": "publicDate",
        "searchType": "range",
        "from": "2026-10-16",
        "to": "2026-10-17",
    }
    assert filters[1] == {
        "fieldName": "type",
        "searchType": "in",
        "fieldValues": ["es-notify-contractor"],
    }
    assert filters[2] == {
        "fieldName": "caseKHKQ",
        "searchType": "not_in",
        "fieldValues": ["1"],
    }


def test_build_kqlcnt_search_payload_structure() -> None:
    payload = build_kqlcnt_search_payload(
        page_number=0,
        page_size=50,
        window_from="2026-10-16",
        window_to="2026-10-17",
    )

    query = payload[0]["query"][0]
    assert query["index"] == "es-contractor-selection"
    filters = query["filters"]
    assert len(filters) == 3
    assert filters[0] == {
        "fieldName": "publicDateKqlcnt",
        "searchType": "range",
        "from": "2026-10-16",
        "to": "2026-10-17",
    }
    assert filters[1] == {
        "fieldName": "type",
        "searchType": "in",
        "fieldValues": ["es-notify-contractor"],
    }
    assert filters[2] == {
        "fieldName": "stepCode",
        "searchType": "in",
        "fieldValues": ["notify-contractor-step-4-kqlcnt"],
    }


def test_build_bid_opening_search_payload_structure() -> None:
    payload = build_bid_opening_search_payload(
        page_number=0,
        page_size=50,
        window_from="2026-10-16",
        window_to="2026-10-17",
    )

    query = payload[0]["query"][0]
    assert query["index"] == "es-contractor-selection"
    filters = query["filters"]
    assert len(filters) == 5
    assert filters[0]["fieldName"] == "publicDate"
    assert filters[1]["fieldName"] == "type"
    assert filters[2]["fieldName"] == "stepCode"
    assert filters[3]["fieldName"] == "publicDateKqmt"
    assert filters[4]["fieldName"] == "isInternet"


def test_build_search_payload_validation() -> None:
    with pytest.raises(ValueError, match="page_number must be greater than or equal to 0"):
        build_project_search_payload(
            page_number=-1,
            page_size=50,
            window_from="2026-10-16",
            window_to="2026-10-17",
        )

    with pytest.raises(ValueError, match="page_size must be greater than 0"):
        build_project_search_payload(
            page_number=0,
            page_size=0,
            window_from="2026-10-16",
            window_to="2026-10-17",
        )

    with pytest.raises(ValueError, match="page_number must be greater than or equal to 0"):
        build_tbmt_search_payload(
            page_number=-1,
            page_size=50,
            window_from="2026-10-16",
            window_to="2026-10-17",
        )

    with pytest.raises(ValueError, match="page_number must be greater than or equal to 0"):
        build_kqlcnt_search_payload(
            page_number=-1,
            page_size=50,
            window_from="2026-10-16",
            window_to="2026-10-17",
        )

    with pytest.raises(ValueError, match="page_number must be greater than or equal to 0"):
        build_bid_opening_search_payload(
            page_number=-1,
            page_size=50,
            window_from="2026-10-16",
            window_to="2026-10-17",
        )


def test_build_search_payload_structure() -> None:
    filters = [{"fieldName": "type", "searchType": "in", "fieldValues": ["test"]}]
    payload = build_search_payload(
        page_number=1,
        page_size=20,
        index="test-index",
        filters=filters,
    )

    assert payload[0]["pageSize"] == 20
    assert payload[0]["pageNumber"] == 1
    assert payload[0]["query"][0]["index"] == "test-index"
    assert payload[0]["query"][0]["filters"] == filters
