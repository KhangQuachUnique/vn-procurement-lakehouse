import logging
from collections.abc import Callable, Iterator
from datetime import date, timedelta

from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

logger = logging.getLogger(__name__)


def iter_daily_windows(
    resource: str, start_date: date, end_date_exclusive: date
) -> Iterator[IngestionWindow]:
    if start_date >= end_date_exclusive:
        raise ValueError("Start date must be before end date exclusive.")

    current_date = start_date

    while current_date < end_date_exclusive:
        yield IngestionWindow(
            resource=resource,
            start_date=current_date,
            end_date_exclusive=current_date + timedelta(days=1),
        )
        current_date += timedelta(days=1)


class IngestDateRange:
    def __init__(self, ingest_daily: IngestDailyWindow) -> None:
        self.ingest_daily = ingest_daily

    def execute(
        self,
        resource: str,
        start_date: date,
        end_date_exclusive: date,
        *,
        force: bool = False,
        continue_on_error: bool = False,
        on_record: Callable[[int], None] | None = None,
    ) -> dict[date, PublishedBatch]:
        results: dict[date, PublishedBatch] = {}

        for window in iter_daily_windows(resource, start_date, end_date_exclusive):
            try:
                published_batch = self.ingest_daily.execute(
                    window, force=force, on_record=on_record
                )
                results[window.start_date] = published_batch
            except Exception as exc:
                if not continue_on_error:
                    raise
                logger.error(
                    "Error ingesting %s for %s: %s. Continuing to next window.",
                    resource,
                    window.start_date,
                    exc,
                )

        return results
