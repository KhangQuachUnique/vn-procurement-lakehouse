from enum import StrEnum
from uuid import UUID

from pydantic.dataclasses import dataclass

from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


class RunStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(eq=False, slots=True)
class IngestionRun:
    run_id: UUID
    window: IngestionWindow
    status: RunStatus = RunStatus.PENDING
    records_ingested: int | None = None

    def start(self) -> None:
        if self.status != RunStatus.PENDING:
            raise ValueError("Run can only be started from PENDING status.")
        self.status = RunStatus.IN_PROGRESS

    def complete(self, records_ingested: int) -> None:
        if self.status != RunStatus.IN_PROGRESS:
            raise ValueError("Run can only be completed from IN_PROGRESS status.")
        if records_ingested < 0:
            raise ValueError("Records ingested cannot be negative.")

        self.status = RunStatus.COMPLETED
        self.records_ingested = records_ingested

    def fail(self) -> None:
        if self.status != RunStatus.IN_PROGRESS:
            raise ValueError("Run can only be failed from IN_PROGRESS status.")
        self.status = RunStatus.FAILED
