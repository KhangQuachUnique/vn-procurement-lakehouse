from collections.abc import Callable, Iterator
from datetime import date, timedelta

from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


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
        on_record: Callable[[int], None] | None = None,
    ) -> dict[date, PublishedBatch]:
        results = {}

        for window in iter_daily_windows(resource, start_date, end_date_exclusive):
            published_batch = self.ingest_daily.execute(
                window, force=force, on_record=on_record
            )
            results[window.start_date] = published_batch

        return results
