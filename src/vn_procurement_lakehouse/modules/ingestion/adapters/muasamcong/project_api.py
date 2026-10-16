from typing import Any

from .client import MuasamcongClient
from .schemas import SearchPage, SearchResponse
from .search import build_project_search_payload

SEARCH_PATH = "/o/egp-portal-contractor-selection-v2/services/smart/search"

PROJECT_DETAIL_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/expose/lcnt/bid-po-bidp-project-view/get-by-id"
)


class ProjectApi:
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
        payload = build_project_search_payload(
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

    def get_project_detail(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        return self._client.post(
            PROJECT_DETAIL_PATH,
            body={"id": project_id},
        )
