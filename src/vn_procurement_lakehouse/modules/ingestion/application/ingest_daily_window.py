import logging
from uuid import uuid4

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    BronzePort,
    RunRepositoryPort,
    SourcePort,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun

logger = logging.getLogger(__name__)


class IngestDailyWindow:
    def __init__(
        self, source: SourcePort, writer: BronzePort, run_repository: RunRepositoryPort
    ) -> None:
        self.source = source
        self.writer = writer
        self.run_repository = run_repository

    def execute(self, window: IngestionWindow) -> PublishedBatch:
        run = IngestionRun(
            run_id=uuid4(),
            window=window,
        )

        self.run_repository.create(run)

        run.start()
        self.run_repository.update(run)

        try:
            records = self.source.fetch(window)
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
