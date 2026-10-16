from datetime import date, timedelta
from uuid import UUID

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    BronzePort,
    RunRepositoryPort,
)
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import VerificationResult


class VerifyBronze:
    def __init__(self, repository: RunRepositoryPort, bronze: BronzePort) -> None:
        self.repository = repository
        self.bronze = bronze

    def verify_run(self, run_id: UUID) -> VerificationResult:
        run = self.repository.get(run_id)
        if run is None:
            raise ValueError(f"Run with ID {run_id} not found.")

        return self.bronze.verify(run)

    def verify_date(self, date: date, resource: str) -> list[VerificationResult]:
        runs = self.repository.list_by_window(
            resource=resource,
            start_date=date,
            end_date_exclusive=date + timedelta(days=1),
        )

        return [self.bronze.verify(run) for run in runs if run.window.resource == resource]
