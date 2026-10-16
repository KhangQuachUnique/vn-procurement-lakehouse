from uuid import UUID

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    BronzePort,
    RunRepositoryPort,
)
from vn_procurement_lakehouse.modules.ingestion.domain.run import RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)


class RecoverIngestionRun:
    def __init__(self, run_repository: RunRepositoryPort, bronze: BronzePort) -> None:
        self.run_repository = run_repository
        self.bronze = bronze

    def recover_run(self, run_id: UUID) -> tuple[bool, VerificationResult | None]:
        run = self.run_repository.get(run_id)
        if run is None:
            raise ValueError(f"Run with ID {run_id} not found.")

        if run.status != RunStatus.IN_PROGRESS:
            raise ValueError(
                f"Run with ID {run_id} is not in IN_PROGRESS status and cannot be recovered."
            )

        verification_result = self.bronze.verify(run)

        if (
            verification_result.status == VerificationStatus.VERIFIED
            and verification_result.record_count is not None
        ):
            run.complete(records_ingested=verification_result.record_count)
        else:
            run.fail()

        self.run_repository.update(run)

        return True, verification_result
