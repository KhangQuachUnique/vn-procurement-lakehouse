from collections.abc import Iterator

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    RawPayload,
)
from vn_procurement_lakehouse.modules.ingestion.domain.models import (
    IngestionWindow,
)


class FakeTenderSource:
    def fetch(
        self,
        ingestion_window: IngestionWindow,
    ) -> Iterator[RawPayload]:
        if ingestion_window.resource != "tbmt":
            raise ValueError(f"Unsupported resource: {ingestion_window.resource}")

        yield {
            "notifyNo": "IB001",
            "notifyVersion": "01",
        }

        yield {
            "notifyNo": "IB002",
            "notifyVersion": "01",
        }
