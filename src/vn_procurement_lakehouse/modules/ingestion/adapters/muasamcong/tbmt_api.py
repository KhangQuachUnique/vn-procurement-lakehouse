from typing import Any

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.client import MuasamcongClient
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
    SearchResponse,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.search import (
    build_tbmt_search_payload,
)

SEARCH_PATH = "/o/egp-portal-contractor-selection-v2/services/smart/search"
STANDARD_DETAIL_PATH = "/o/egp-portal-contractor-selection-v2/services/lcnt_tbmt_ttc_ldt"
REOFFER_DETAIL_PATH = "/o/egp-portal-contractor-selection-v2/services/online-reoffer/detail"
VK_ADB_DETAIL_PATH = "/o/egp-portal-contractor-selection-v2/services/lcnt_tbmt_ttc_vk_adb"


class TbmtApi:
    def __init__(self, client: MuasamcongClient) -> None:
        self._client = client

    def search(
        self, *, page_number: int, page_size: int, window_from: str, window_to: str
    ) -> SearchPage:
        payload = build_tbmt_search_payload(
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

    def get_standard_detail(self, notice_id: str) -> dict[str, Any]:
        return self._client.post(STANDARD_DETAIL_PATH, {"id": notice_id})

    def get_reoffer_detail(self, notice_id: str) -> dict[str, Any]:
        return self._client.post(REOFFER_DETAIL_PATH, {"id": notice_id})

    def get_vk_adb_detail(self, notice_id: str) -> dict[str, Any]:
        return self._client.post(VK_ADB_DETAIL_PATH, {"id": notice_id})

    def get_notice_detail(self, search_item: dict[str, Any]) -> dict[str, Any]:
        notice_id = search_item.get("id")
        if not notice_id:
            raise KeyError("Search item missing id")

        notice_id_str = str(notice_id)
        bid_form = search_item.get("bidForm")
        step_code = search_item.get("stepCode")
        process_apply = search_item.get("processApply")

        if bid_form == "CGTTRG" or (
            isinstance(step_code, str) and step_code.startswith("reoffer-price-")
        ):
            return self.get_reoffer_detail(notice_id_str)
        if process_apply in ("KHAC", "WB", "ADB"):
            return self.get_vk_adb_detail(notice_id_str)

        return self.get_standard_detail(notice_id_str)


# Backwards compatibility alias
TBMTApi = TbmtApi
