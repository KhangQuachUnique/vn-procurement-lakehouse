from typing import Any

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.client import MuasamcongClient
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.schemas import (
    SearchPage,
    SearchResponse,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.search import (
    build_bid_opening_search_payload,
)

SEARCH_PATH = "/o/egp-portal-contractor-selection-v2/services/smart/search"
NOTIFY_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/exposeldtkqmt/bid-notification-p/notify"
)
ROUNDMNG_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/expose/ldtkqmt/bid-notification-p/roundmng"
)
BID_OPEN_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/expose/ldtkqmt/bid-notification-p/bid-open"
)
LOT_OPEN_PATH = (
    "/o/egp-portal-contractor-selection-v2/services/expose/ldtkqmt/bid-notification-p/lotOpenDetail"
)

DUAL_STAGE_MODE = "1_HTHS"


class BidOpeningApi:
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
        payload = build_bid_opening_search_payload(
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

    def get_bid_opening_detail(self, search_item: dict[str, Any]) -> dict[str, Any]:
        notify_id = search_item.get("notifyId") or search_item.get("id")
        notify_no = search_item.get("notifyNo")

        if not notify_id or not str(notify_id).strip():
            raise KeyError("Search item missing notifyId or id")

        if not notify_no or not str(notify_no).strip():
            raise KeyError("Search item missing notifyNo")

        base_body: dict[str, Any] = {
            "notifyId": str(notify_id),
            "notifyNo": str(notify_no),
            "type": "TBMT",
            "packType": 0,
        }

        notify_payload = self._client.post(NOTIFY_PATH, base_body)
        roundmng_payload = self._client.post(ROUNDMNG_PATH, base_body)

        if not notify_payload and not roundmng_payload:
            return {}

        result: dict[str, Any] = {
            "searchMetadata": search_item,
            "notify": notify_payload,
            "roundmng": roundmng_payload,
        }

        # Check single vs dual stage
        round_dto = roundmng_payload.get("bidoBidroundMngViewDTO")
        round_dto_dict = round_dto if isinstance(round_dto, dict) else {}
        bid_mode = search_item.get("bidMode") or round_dto_dict.get("bidMode")

        if bid_mode == DUAL_STAGE_MODE:
            req_tech = {**base_body, "packType": 1, "viewType": 0}
            result["bid_open_technical"] = self._client.post(BID_OPEN_PATH, req_tech)
            result["lot_open_detail_technical"] = self._client.post_array(LOT_OPEN_PATH, req_tech)

            if round_dto_dict.get("successBidOpenDateTc") is not None:
                req_fin = {**base_body, "packType": 2, "viewType": 0}
                result["bid_open_financial"] = self._client.post(BID_OPEN_PATH, req_fin)
                result["lot_open_detail_financial"] = self._client.post_array(
                    LOT_OPEN_PATH, req_fin
                )
        else:
            result["bid_open"] = self._client.post(BID_OPEN_PATH, base_body)
            result["lot_open_detail"] = self._client.post_array(LOT_OPEN_PATH, base_body)

        return result
