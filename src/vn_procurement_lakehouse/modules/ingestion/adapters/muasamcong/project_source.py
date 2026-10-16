from collections.abc import Iterator
from typing import Any

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    RawPayload,
)
from vn_procurement_lakehouse.modules.ingestion.domain.models import (
    IngestionWindow,
)

from .concurrency import iter_concurrent_details
from .project_api import ProjectApi


class IncompleteIngestionError(RuntimeError):
    """Source could not fetch all expected records."""


class ProjectSource:
    def __init__(
        self,
        api: ProjectApi,
        *,
        page_size: int = 50,
        workers: int = 3,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if workers <= 0:
            raise ValueError("workers must be positive")

        self._api = api
        self._page_size = page_size
        self._workers = workers

    def fetch(
        self,
        ingestion_window: IngestionWindow,
    ) -> Iterator[RawPayload]:
        if ingestion_window.resource != "project":
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
                project_id = item.get("id")

                if not isinstance(project_id, str) or not project_id.strip():
                    raise IncompleteIngestionError("Project search item missing valid id")

                if project_id in seen_ids:
                    raise IncompleteIngestionError(f"Duplicate project id: {project_id}")

                seen_ids.add(project_id)

            def _fetch_item_detail(item: dict[str, Any]) -> RawPayload:
                project_id = item.get("id")
                assert isinstance(project_id, str)

                detail = self._api.get_project_detail(project_id)

                if not isinstance(detail, dict) or not detail:
                    raise IncompleteIngestionError(f"Invalid detail for project {project_id}")

                return detail

            yield from iter_concurrent_details(
                page.content, _fetch_item_detail, max_workers=self._workers
            )

            if len(seen_ids) > expected_total:
                raise IncompleteIngestionError("Received more records than expected")

            if page_number == expected_pages - 1:
                if len(seen_ids) != expected_total:
                    raise IncompleteIngestionError(
                        f"Incomplete ingestion: expected {expected_total}, received {len(seen_ids)}"
                    )
                break

            page_number += 1
