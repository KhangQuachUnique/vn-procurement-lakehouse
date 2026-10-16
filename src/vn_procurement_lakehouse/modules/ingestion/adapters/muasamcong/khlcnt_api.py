from typing import Any

from .client import MuasamcongClient
from .schemas import SearchPage, SearchResponse
from .search import build_khlcnt_search_payload

SEARCH_PATH = "/o/egp-portal-contractor-selection-v2/services/smart/search"

PLAN_DETAIL_PATH = "/o/egp-portal-contractor-selection-v2/services/expose/lcnt/bid-po-bidp-plan-project-view/get-by-id"

PACKAGE_DETAIL_PATH = "/o/egp-portal-contractor-selection-v2/services/lcnt/bid-po-bidp-plan-project-view/get-bidp-plan-detail-by-id"


class KhlcntApi:
    def __init__(self, client: MuasamcongClient) -> None:
        self._client = client

    def search(
        self,
        *,
        page_number: int,
        page_size: int,
        window_from: str,
        window_to: str,
    ) -> SearchPage:
        payload = build_khlcnt_search_payload(
            page_number=page_number,
            page_size=page_size,
            window_from=window_from,
            window_to=window_to,
        )

        response = self._client.post(
            SEARCH_PATH,
            body=payload,
        )

        return SearchResponse.model_validate(response).page

    def get_plan_detail(
        self,
        plan_id: str,
    ) -> dict[str, Any]:
        return self._client.post(
            PLAN_DETAIL_PATH,
            body={"id": plan_id},
        )

    def get_bid_package_detail(
        self,
        package_id: str,
    ) -> dict[str, Any]:
        return self._client.post(
            PACKAGE_DETAIL_PATH,
            body={"id": package_id},
        )
