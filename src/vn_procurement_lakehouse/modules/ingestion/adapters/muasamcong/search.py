from typing import Any

PROJECT_INDEX = "es-contractor-selection"
PROJECT_TYPE = "es-bidp-project-p"

KHLCNT_INDEX = "es-contractor-selection"
KHLCNT_TYPE = "es-plan-project-p"

TBMT_INDEX = "es-contractor-selection"
TBMT_TYPE = "es-notify-contractor"
TBMT_CASE_KHKQ_EXCLUDED = "1"

KQLCNT_INDEX = "es-contractor-selection"
KQLCNT_TYPE = "es-notify-contractor"
KQLCNT_STEP_CODE = "notify-contractor-step-4-kqlcnt"

BID_OPENING_INDEX = "es-contractor-selection"
BID_OPENING_TYPE = "es-notify-contractor"
BID_OPENING_STEP_CODES = [
    "notify-contractor-step-2-kqmt",
    "notify-contractor-step-3-dsntdkt",
    "notify-contractor-step-4-kqlcnt",
]


def build_khlcnt_search_payload(
    *,
    page_number: int,
    page_size: int,
    window_from: str,
    window_to: str,
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": KHLCNT_INDEX,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": [
                        {
                            "fieldName": "publicDate",
                            "searchType": "range",
                            "from": window_from,
                            "to": window_to,
                        },
                        {
                            "fieldName": "type",
                            "searchType": "in",
                            "fieldValues": [KHLCNT_TYPE],
                        },
                    ],
                }
            ],
        }
    ]


def build_project_search_payload(
    *,
    page_number: int,
    page_size: int,
    window_from: str,
    window_to: str,
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": PROJECT_INDEX,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": [
                        {
                            "fieldName": "publicDate",
                            "searchType": "range",
                            "from": window_from,
                            "to": window_to,
                        },
                        {
                            "fieldName": "type",
                            "searchType": "in",
                            "fieldValues": [PROJECT_TYPE],
                        },
                    ],
                }
            ],
        }
    ]


def build_tbmt_search_payload(
    *,
    page_number: int,
    page_size: int,
    window_from: str,
    window_to: str,
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": TBMT_INDEX,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": [
                        {
                            "fieldName": "publicDate",
                            "searchType": "range",
                            "from": window_from,
                            "to": window_to,
                        },
                        {
                            "fieldName": "type",
                            "searchType": "in",
                            "fieldValues": [TBMT_TYPE],
                        },
                        {
                            "fieldName": "caseKHKQ",
                            "searchType": "not_in",
                            "fieldValues": [TBMT_CASE_KHKQ_EXCLUDED],
                        },
                    ],
                }
            ],
        }
    ]


def build_kqlcnt_search_payload(
    *,
    page_number: int,
    page_size: int,
    window_from: str,
    window_to: str,
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": KQLCNT_INDEX,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": [
                        {
                            "fieldName": "publicDateKqlcnt",
                            "searchType": "range",
                            "from": window_from,
                            "to": window_to,
                        },
                        {
                            "fieldName": "type",
                            "searchType": "in",
                            "fieldValues": [KQLCNT_TYPE],
                        },
                        {
                            "fieldName": "stepCode",
                            "searchType": "in",
                            "fieldValues": [KQLCNT_STEP_CODE],
                        },
                    ],
                }
            ],
        }
    ]


def build_bid_opening_search_payload(
    *,
    page_number: int,
    page_size: int,
    window_from: str,
    window_to: str,
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": BID_OPENING_INDEX,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": [
                        {
                            "fieldName": "publicDate",
                            "searchType": "range",
                            "from": window_from,
                            "to": window_to,
                        },
                        {
                            "fieldName": "type",
                            "searchType": "in",
                            "fieldValues": [BID_OPENING_TYPE],
                        },
                        {
                            "fieldName": "stepCode",
                            "searchType": "in",
                            "fieldValues": BID_OPENING_STEP_CODES,
                        },
                        {
                            "fieldName": "publicDateKqmt",
                            "searchType": "not_null",
                            "fieldValues": [""],
                        },
                        {
                            "fieldName": "isInternet",
                            "searchType": "in",
                            "fieldValues": [1],
                        },
                    ],
                }
            ],
        }
    ]


def build_search_payload(
    *, page_number: int, page_size: int, index: str, filters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if page_number < 0:
        raise ValueError("page_number must be greater than or equal to 0")

    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    return [
        {
            "pageSize": page_size,
            "pageNumber": page_number,
            "query": [
                {
                    "index": index,
                    "matchType": "all-1",
                    "matchFields": ["notifyNo", "bidName"],
                    "filters": filters,
                }
            ],
        }
    ]
