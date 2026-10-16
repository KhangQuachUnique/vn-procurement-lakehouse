import logging
from collections.abc import Iterator

from vn_procurement_lakehouse.modules.ingestion.application.ports import RawPayload
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow

from .kqlcnt_api import KqlcntApi

logger = logging.getLogger(__name__)


class IncompleteIngestionError(RuntimeError):
    """Source could not fetch all expected records."""


class KqlcntSource:
    def __init__(
        self,
        api: KqlcntApi,
        *,
        page_size: int = 50,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")

        self._api = api
        self._page_size = page_size

    def fetch(
        self,
        ingestion_window: IngestionWindow,
    ) -> Iterator[RawPayload]:
        if ingestion_window.resource != "kqlcnt":
            raise ValueError(f"Unsupported resource: {ingestion_window.resource}")

        return self._fetch_records(ingestion_window)

    def _fetch_records(
        self,
        ingestion_window: IngestionWindow,
    ) -> Iterator[RawPayload]:
        page_number = 0
        expected_total: int | None = None
        expected_pages: int | None = None
        seen_ids: set[str] = set()

        while True:
            page = self._api.search(
                page_number=page_number,
                page_size=self._page_size,
                window_from=ingestion_window.start_date.isoformat(),
                window_to=ingestion_window.end_date_exclusive.isoformat(),
            )

            # Validate pagination metadata
            if page.current_page != page_number:
                raise IncompleteIngestionError(
                    f"Expected page {page_number}, received {page.current_page}"
                )

            if page.page_size != self._page_size:
                raise IncompleteIngestionError("Unexpected page size")

            if expected_total is None:
                expected_total = page.total_elements
                expected_pages = page.total_pages
            elif page.total_elements != expected_total or page.total_pages != expected_pages:
                raise IncompleteIngestionError("Pagination metadata changed during ingestion")

            # Validate page structure and boundaries
            assert expected_total is not None
            assert expected_pages is not None

            if expected_total == 0:
                if page.content:
                    raise IncompleteIngestionError("Invalid empty search result")
                break

            if expected_pages == 0 or page_number >= expected_pages or not page.content:
                raise IncompleteIngestionError("Pagination ended unexpectedly")

            if len(page.content) > self._page_size:
                raise IncompleteIngestionError("Page exceeds configured size")

            for item in page.content:
                result_id = item.get("inputResultId") or item.get("id")

                if not isinstance(result_id, str) or not result_id.strip():
                    raise IncompleteIngestionError("KQLCNT search item missing valid id")

                if result_id in seen_ids:
                    raise IncompleteIngestionError(f"Duplicate KQLCNT id: {result_id}")

                seen_ids.add(result_id)

                result_detail = self._api.get_result_detail(result_id)

                if not isinstance(result_detail, dict) or not result_detail:
                    raise IncompleteIngestionError(f"Invalid detail for KQLCNT {result_id}")

                # Attach search-level metadata to detail if not present
                if "searchMetadata" not in result_detail:
                    result_detail["searchMetadata"] = item

                yield result_detail

            if len(seen_ids) > expected_total:
                raise IncompleteIngestionError("Received more records than expected")

            if page_number == expected_pages - 1:
                if len(seen_ids) != expected_total:
                    raise IncompleteIngestionError(
                        f"Incomplete ingestion: expected {expected_total}, received {len(seen_ids)}"
                    )
                break

            page_number += 1
