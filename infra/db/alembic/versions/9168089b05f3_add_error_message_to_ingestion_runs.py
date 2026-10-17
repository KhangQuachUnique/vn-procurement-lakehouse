"""add error_message to ingestion_runs

Revision ID: 9168089b05f3
Revises: be973556bb8f
Create Date: 2026-10-16 23:01:13.342730

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9168089b05f3"
down_revision: str | Sequence[str] | None = "be973556bb8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "ingestion_runs",
        sa.Column("error_message", sa.Text(), nullable=True),
        schema="control",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ingestion_runs", "error_message", schema="control")
