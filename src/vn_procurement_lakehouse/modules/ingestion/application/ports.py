from collections.abc import Iterable, Iterator
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from vn_procurement_lakehouse.modules.ingestion.domain.batch import PublishedBatch
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import VerificationResult
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

RawPayload = dict[str, Any]


class SourcePort(Protocol):
    def fetch(self, ingestion_window: IngestionWindow) -> Iterator[RawPayload]: ...


class BronzePort(Protocol):
    def write(
        self, window: IngestionWindow, records: Iterable[RawPayload], *, run_id: UUID
    ) -> PublishedBatch: ...

    def verify(self, run: IngestionRun) -> VerificationResult: ...


class RunRepositoryPort(Protocol):
    def create(self, run: IngestionRun) -> None: ...

    def update(self, run: IngestionRun) -> None: ...

    def get(self, run_id: UUID) -> IngestionRun | None: ...

    def list_by_window(
        self, resource: str, start_date: date, end_date_exclusive: date
    ) -> list[IngestionRun]: ...

    def complete_if_running(self, run_id: UUID, records_ingested: int) -> bool: ...
