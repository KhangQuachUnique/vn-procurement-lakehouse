import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    BronzePort,
    RawPayload,
    RunRepositoryPort,
    SourcePort,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import VerificationStatus
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

logger = logging.getLogger(__name__)


class IngestDailyWindow:
    def __init__(
        self, source: SourcePort, writer: BronzePort, run_repository: RunRepositoryPort
    ) -> None:
        self.source = source
        self.writer = writer
        self.run_repository = run_repository

    def execute(
        self,
        window: IngestionWindow,
        *,
        force: bool = False,
        on_record: Callable[[int], None] | None = None,
    ) -> PublishedBatch:
        if not force:
            existing_runs = self.run_repository.list_by_window(
                window.resource, window.start_date, window.end_date_exclusive
            )
            for existing_run in existing_runs:
                if existing_run.status == RunStatus.COMPLETED:
                    verification = self.writer.verify(existing_run)
                    if verification.status == VerificationStatus.VERIFIED:
                        base_path = Path(getattr(self.writer, "base_path", "data/bronze"))
                        storage_uri = str(
                            base_path
                            / window.resource
                            / f"date={window.start_date.isoformat()}"
                            / "runs"
                            / str(existing_run.run_id)
                            / "part-000.jsonl"
                        )
                        record_count = (
                            verification.record_count
                            if verification.record_count is not None
                            else (existing_run.records_ingested or 0)
                        )
                        return PublishedBatch(
                            run_id=existing_run.run_id,
                            record_count=record_count,
                            storage_uri=storage_uri,
                            skipped=True,
                        )

        run = IngestionRun(
            run_id=uuid4(),
            window=window,
        )

        self.run_repository.create(run)

        run.start()
        self.run_repository.update(run)

        def _counted_records() -> Iterator[RawPayload]:
            count = 0
            for record in self.source.fetch(window):
                count += 1
                if on_record is not None:
                    on_record(count)
                yield record

        try:
            records = _counted_records() if on_record else self.source.fetch(window)
            published_batch = self.writer.write(window, records, run_id=run.run_id)

        except Exception:
            run.fail()

            try:
                self.run_repository.update(run)
            except Exception:
                logger.exception(
                    "Cannot persist failed status for run %s",
                    run.run_id,
                )
            raise

        run.complete(records_ingested=published_batch.record_count)
        self.run_repository.update(run)

        return published_batch
