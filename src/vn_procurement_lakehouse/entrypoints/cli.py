from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from vn_procurement_lakehouse.bootstrap.container import (
    coverage_scope,
    ingestion_scope,
    recover_ingestion_scope,
    verify_bronze_scope,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.composite_source import (
    normalize_resource_name,
)
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

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
    force: Annotated[
        bool, typer.Option("--force", help="Force re-ingest even if already verified")
    ] = False,
) -> None:
    parsed_date = parse_date(day)

    window = IngestionWindow(
        resource=resource,
        start_date=parsed_date,
        end_date_exclusive=parsed_date + timedelta(days=1),
    )

    console = Console()
    with ingestion_scope() as service:
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[{resource} {parsed_date.isoformat()}]"),
            TextColumn("{task.description}"),
            TextColumn("• {task.completed} records"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Ingesting...", total=None)
            batch = service.ingestion_daily.execute(
                window,
                force=force,
                on_record=lambda count: progress.update(task, completed=count),
            )

    if batch.skipped:
        typer.echo(
            f"[SKIP] Resource '{resource}' on {parsed_date} already verified.\n"
            f"Run ID: {batch.run_id}\n"
            f"Bronze: {batch.storage_uri}\n"
            f"Use --force to re-ingest."
        )
    else:
        typer.echo(f"Ingested {batch.record_count} records for {parsed_date}")
        typer.echo(f"Run ID: {batch.run_id}")
        typer.echo(f"Bronze: {batch.storage_uri}")


@app.command(name="ingest-range", help="Ingest data for a range of dates into the lakehouse")
def ingest_range(
    resource: Annotated[str, typer.Argument(callback=validate_resource)],
    start: Annotated[str, typer.Option("--start")],
    end: Annotated[str, typer.Option("--end")],
    force: Annotated[
        bool, typer.Option("--force", help="Force re-ingest even if already verified")
    ] = False,
) -> None:
    start_date = parse_date(start)
    end_date = parse_date(end)

    if start_date >= end_date:
        raise typer.BadParameter(
            f"Start date {start_date.isoformat()} must be before end date {end_date.isoformat()}."
        )

    console = Console()
    with ingestion_scope() as service:
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[{resource}]"),
            TextColumn("{task.description}"),
            TextColumn("• {task.completed} records"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Ingesting {start_date} to {end_date}...", total=None)

            def _on_record(count: int) -> None:
                progress.update(task, completed=count)

            results = service.ingestion_range.execute(
                resource, start_date, end_date, force=force, on_record=_on_record
            )

    for day, batch in results.items():
        if batch.skipped:
            typer.echo(f"[SKIP] {day}: already verified (Run ID: {batch.run_id})")
        else:
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


@app.command(name="coverage", help="Check data coverage for a resource across a date range")
def coverage(
    resource: Annotated[str, typer.Argument(callback=validate_resource)],
    start: Annotated[str, typer.Option("--start")],
    end: Annotated[str, typer.Option("--end")],
    missing_only: Annotated[
        bool, typer.Option("--missing-only", help="Show only missing or failed days")
    ] = False,
) -> None:
    start_date = parse_date(start)
    end_date = parse_date(end)

    if start_date >= end_date:
        raise typer.BadParameter(
            f"Start date {start_date.isoformat()} must be before end date {end_date.isoformat()}."
        )

    console = Console()
    with coverage_scope() as service:
        days = service.data_coverage.execute(
            resource, start_date, end_date, missing_only=missing_only
        )

    table = Table(title=f"Bronze Data Coverage: {resource.upper()} ({start_date} -> {end_date})")
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Records", justify="right")
    table.add_column("Run ID", style="dim")
    table.add_column("Storage URI", style="dim")

    for day in days:
        if day.status == "VERIFIED":
            status_display = "[green]VERIFIED[/green]"
        elif day.status == "FAILED":
            status_display = "[red]FAILED[/red]"
        elif day.status == "MISSING":
            status_display = "[dim red]MISSING[/dim red]"
        elif day.status == "IN_PROGRESS":
            status_display = "[yellow]IN_PROGRESS[/yellow]"
        else:
            status_display = day.status

        records_display = str(day.record_count) if day.record_count is not None else "-"
        run_id_display = str(day.run_id) if day.run_id else "-"
        storage_display = str(day.storage_uri) if day.storage_uri else "-"

        table.add_row(
            day.date.isoformat(),
            status_display,
            records_display,
            run_id_display,
            storage_display,
        )

    total_days = len(days)
    verified_days = sum(1 for d in days if d.status == "VERIFIED")
    missing_days = sum(1 for d in days if d.status == "MISSING")
    failed_days = sum(1 for d in days if d.status in ("FAILED", "CORRUPTED"))

    console.print(table)
    console.print(
        f"[bold]Summary:[/bold] {total_days} total days | "
        f"[green]{verified_days} verified[/green] | "
        f"[dim red]{missing_days} missing[/dim red] | "
        f"[red]{failed_days} failed[/red]"
    )

