from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

import typer

from vn_procurement_lakehouse.bootstrap.container import (
    ingestion_scope,
    recover_ingestion_scope,
    verify_bronze_scope,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.composite_source import (
    normalize_resource_name,
)
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow

app = typer.Typer(name="vn-procurement-lakehouse", help="A CLI for the VN Procurement Lakehouse")


@app.callback()
def main() -> None:
    """Vietnam Procurement Lakehouse."""


SUPPORTED_RESOURCES = frozenset({"project", "khlcnt", "tbmt", "kqlcnt", "bid_opening"})


def validate_resource(resource: str) -> str:
    normalized = normalize_resource_name(resource)
    if normalized not in SUPPORTED_RESOURCES:
        supported = ", ".join(sorted(SUPPORTED_RESOURCES))
        raise typer.BadParameter(
            f"Unsupported resource '{resource}'. Supported resources: {supported}."
        )
    return normalized


def parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except ValueError as exc:
        raise typer.BadParameter(
            f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD."
        ) from exc


@app.command(name="ingest", help="Ingest data into the lakehouse")
def ingest(
    resource: Annotated[str, typer.Argument(callback=validate_resource)],
    day: Annotated[str, typer.Option("--date")],
) -> None:
    parsed_date = parse_date(day)

    window = IngestionWindow(
        resource=resource,
        start_date=parsed_date,
        end_date_exclusive=parsed_date + timedelta(days=1),
    )

    with ingestion_scope() as service:
        typer.echo(f"Ingesting data for resource '{resource}' on {parsed_date.isoformat()}...")
        batch = service.ingestion_daily.execute(window)

    typer.echo(f"Ingested {batch.record_count} records for {parsed_date}")

    typer.echo(f"Run ID: {batch.run_id}")
    typer.echo(f"Bronze: {batch.storage_uri}")


@app.command(name="ingest-range", help="Ingest data for a range of dates into the lakehouse")
def ingest_range(
    resource: Annotated[str, typer.Argument(callback=validate_resource)],
    start: Annotated[str, typer.Option("--start")],
    end: Annotated[str, typer.Option("--end")],
) -> None:
    start_date = parse_date(start)
    end_date = parse_date(end)

    if start_date >= end_date:
        raise typer.BadParameter(
            f"Start date {start_date.isoformat()} must be before end date {end_date.isoformat()}."
        )

    with ingestion_scope() as service:
        results = service.ingestion_range.execute(resource, start_date, end_date)

    for day, batch in results.items():
        typer.echo(f"Ingested {batch.record_count} records for {day}")
        typer.echo(f"Run ID: {batch.run_id}")
        typer.echo(f"Bronze: {batch.storage_uri}")


@app.command(name="bronze-verify-run", help="Verify ingested data in the lakehouse")
def verify_run(
    run_id: Annotated[UUID, typer.Argument()],
) -> None:
    with verify_bronze_scope() as service:
        result = service.verify_bronze.verify_run(run_id)

    typer.echo(f"Verification result for run {run_id}:")
    typer.echo(f"Run ID: {result.run_id}")
    typer.echo(f"Status: {result.status.value}")
    typer.echo(f"Record count: {result.record_count}")
    typer.echo(f"Reason: {result.reason if result.reason else 'N/A'}")


@app.command(
    name="bronze-verify-window", help="Verify ingested data for a date window in the lakehouse"
)
def verify_window(
    resource: Annotated[str, typer.Argument(callback=validate_resource)],
    day: Annotated[str, typer.Option("--date")],
) -> None:
    parsed_date = parse_date(day)

    with verify_bronze_scope() as service:
        results = service.verify_bronze.verify_date(resource=resource, date=parsed_date)

    for result in results:
        typer.echo(f"Verification result for {day}:")
        typer.echo(f"Run ID: {result.run_id}")
        typer.echo(f"Status: {result.status.value}")
        typer.echo(f"Record count: {result.record_count}")
        typer.echo(f"Reason: {result.reason if result.reason else 'N/A'}")


@app.command(
    name="bronze-recover",
    help="Manually recover an interrupted ingestion run",
)
def bronze_recover(
    run_id: Annotated[
        UUID,
        typer.Option("--run-id"),
    ],
) -> None:
    with recover_ingestion_scope() as service:
        confirmed = typer.confirm(
            "Have you confirmed the ingestion process is no longer running?",
            default=False,
        )

        if not confirmed:
            typer.echo("Recovery cancelled.")
            return

        updated, verification = service.recover_ingestion_run.recover_run(run_id)

    if verification is None:
        typer.echo("Run is no longer IN_PROGRESS.")
        return

    typer.echo(f"Verification: {verification.status.value}")

    if not updated:
        typer.echo(f"Recovery skipped: {verification.reason or 'No update performed'}")
        raise typer.Exit(code=1)

    typer.echo("Recovery successful: IN_PROGRESS -> COMPLETED")
    typer.echo(f"Record count: {verification.record_count}")
