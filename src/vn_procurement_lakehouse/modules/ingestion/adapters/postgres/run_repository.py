from datetime import date
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.models import IngestionRunRow
from vn_procurement_lakehouse.modules.ingestion.domain.run import IngestionRun, RunStatus
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


class PostgresRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, run: IngestionRun) -> None:
        row = IngestionRunRow(
            run_id=run.run_id,
            resource=run.window.resource,
            start_date=run.window.start_date,
            end_date_exclusive=run.window.end_date_exclusive,
            status=run.status.value,
            record_count=run.records_ingested,
            error_message=run.error_message,
        )

        with self._session_factory.begin() as session:
            session.add(row)

    def update(self, run: IngestionRun) -> None:
        with self._session_factory.begin() as session:
            row = session.get(IngestionRunRow, run.run_id)
            if row is None:
                raise ValueError(f"Ingestion run with ID {run.run_id} not found.")

            row.status = run.status.value
            row.record_count = run.records_ingested
            row.error_message = run.error_message

    def get(self, run_id: UUID) -> IngestionRun | None:
        with self._session_factory() as session:
            row = session.get(IngestionRunRow, run_id)
            if row is None:
                return None

            window = IngestionWindow(
                resource=row.resource,
                start_date=row.start_date,
                end_date_exclusive=row.end_date_exclusive,
            )

            return IngestionRun(
                run_id=row.run_id,
                window=window,
                status=RunStatus(row.status),
                records_ingested=row.record_count,
                error_message=row.error_message,
            )

    def list_by_window(
        self, resource: str, start_date: date, end_date_exclusive: date
    ) -> list[IngestionRun]:
        with self._session_factory() as session:
            rows = (
                session.query(IngestionRunRow)
                .filter(
                    IngestionRunRow.resource == resource,
                    IngestionRunRow.start_date >= start_date,
                    IngestionRunRow.end_date_exclusive <= end_date_exclusive,
                )
                .all()
            )

            runs = []
            for row in rows:
                window = IngestionWindow(
                    resource=row.resource,
                    start_date=row.start_date,
                    end_date_exclusive=row.end_date_exclusive,
                )
                run = IngestionRun(
                    run_id=row.run_id,
                    window=window,
                    status=RunStatus(row.status),
                    records_ingested=row.record_count,
                    error_message=row.error_message,
                )
                runs.append(run)

            return runs

    def complete_if_running(self, run_id: UUID, records_ingested: int) -> bool:
        if records_ingested < 0:
            raise ValueError("records_ingested must be a non-negative integer.")

        stmt = (
            update(IngestionRunRow)
            .where(
                IngestionRunRow.run_id == run_id,
                IngestionRunRow.status == RunStatus.IN_PROGRESS.value,
            )
            .values(
                status=RunStatus.COMPLETED.value,
                record_count=records_ingested,
            )
            .returning(IngestionRunRow.run_id)
        )

        with self._session_factory.begin() as session:
            updated_run_id = session.scalar(stmt)

        return updated_run_id is not None
