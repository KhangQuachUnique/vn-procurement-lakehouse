from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class IngestionRunRow(Base):
    __tablename__ = "ingestion_runs"

    __table_args__ = (
        CheckConstraint(
            "resource ~ '^[a-z][a-z0-9_]*$'",
            name="ck_ingestion_runs_resource",
        ),
        CheckConstraint(
            "end_date_exclusive = start_date + 1",
            name="ck_ingestion_runs_daily_window",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_ingestion_runs_status",
        ),
        CheckConstraint(
            """
            (
                status = 'COMPLETED'
                AND record_count IS NOT NULL
                AND record_count >= 0
            )
            OR
            (
                status <> 'COMPLETED'
                AND record_count IS NULL
            )
            """,
            name="ck_ingestion_runs_record_count",
        ),
        Index(
            "ix_ingestion_runs_resource_day",
            "resource",
            "start_date",
            "created_at",
        ),
        {"schema": "control"},
    )

    run_id: Mapped[UUID] = mapped_column(primary_key=True)

    resource: Mapped[str] = mapped_column(Text, nullable=False)

    start_date: Mapped[date] = mapped_column(nullable=False)

    end_date_exclusive: Mapped[date] = mapped_column(nullable=False)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="PENDING",
    )

    record_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
