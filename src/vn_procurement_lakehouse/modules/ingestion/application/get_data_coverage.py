from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    BronzePort,
    RunRepositoryPort,
)
from vn_procurement_lakehouse.modules.ingestion.domain.coverage import DayCoverage
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import VerificationStatus


def iter_dates(start_date: date, end_date_exclusive: date) -> Iterator[date]:
    if start_date >= end_date_exclusive:
        raise ValueError("Start date must be before end date exclusive.")
    current = start_date
    while current < end_date_exclusive:
        yield current
        current += timedelta(days=1)


class GetDataCoverage:
    def __init__(self, repository: RunRepositoryPort, bronze: BronzePort) -> None:
        self.repository = repository
        self.bronze = bronze

    def execute(
        self,
        resource: str,
        start_date: date,
        end_date_exclusive: date,
        *,
        missing_only: bool = False,
    ) -> list[DayCoverage]:
        all_runs = self.repository.list_by_window(resource, start_date, end_date_exclusive)
        runs_by_date: dict[date, list[IngestionRun]] = {}
        for run in all_runs:
            runs_by_date.setdefault(run.window.start_date, []).append(run)

        base_path = Path(getattr(self.bronze, "base_path", "data/bronze"))
        days: list[DayCoverage] = []

        for current_day in iter_dates(start_date, end_date_exclusive):
            runs_for_day = runs_by_date.get(current_day, [])
            if not runs_for_day:
                days.append(
                    DayCoverage(
                        date=current_day,
                        status="MISSING",
                        record_count=None,
                        run_id=None,
                        storage_uri=None,
                    )
                )
                continue

            verified_run: IngestionRun | None = None
            verified_record_count: int | None = None
            failed_run: IngestionRun | None = None

            for run in runs_for_day:
                if run.status == RunStatus.COMPLETED:
                    verification = self.bronze.verify(run)
                    if verification.status == VerificationStatus.VERIFIED:
                        verified_run = run
                        verified_record_count = (
                            verification.record_count
                            if verification.record_count is not None
                            else run.records_ingested
                        )
                        break
                elif run.status == RunStatus.FAILED:
                    failed_run = run

            if verified_run is not None:
                storage_uri = str(
                    base_path
                    / resource
                    / f"date={current_day.isoformat()}"
                    / "runs"
                    / str(verified_run.run_id)
                    / "part-000.jsonl"
                )
                days.append(
                    DayCoverage(
                        date=current_day,
                        status="VERIFIED",
                        record_count=verified_record_count,
                        run_id=verified_run.run_id,
                        storage_uri=storage_uri,
                    )
                )
            elif failed_run is not None:
                days.append(
                    DayCoverage(
                        date=current_day,
                        status="FAILED",
                        record_count=failed_run.records_ingested,
                        run_id=failed_run.run_id,
                        storage_uri=None,
                    )
                )
            else:
                latest_run = runs_for_day[-1]
                days.append(
                    DayCoverage(
                        date=current_day,
                        status=latest_run.status.value,
                        record_count=latest_run.records_ingested,
                        run_id=latest_run.run_id,
                        storage_uri=None,
                    )
                )

        if missing_only:
            days = [d for d in days if d.status in ("MISSING", "FAILED", "CORRUPTED")]

        return days
