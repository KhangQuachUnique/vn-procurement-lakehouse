from typing import Any

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.client import MuasamcongClient
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
    SearchResponse,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.search import (
    build_kqlcnt_search_payload,
)

SEARCH_PATH = "/o/egp-portal-contractor-selection-v2/services/smart/search"
CONTRACTOR_RESULT_DETAIL_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/expose/contractor-input-result/get"
)


class KqlcntApi:
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
        payload = build_kqlcnt_search_payload(
            page_number=page_number,
            page_size=page_size,
            window_from=window_from,
            window_to=window_to,
        )

        response = self._client.post(
            path=SEARCH_PATH,
            body=payload,
        )

        return SearchResponse.model_validate(response).page

    def get_result_detail(self, result_id: str) -> dict[str, Any]:
        return self._client.post(CONTRACTOR_RESULT_DETAIL_PATH, {"id": result_id})
