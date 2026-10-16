import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BronzeManifest:
    schema_version: int
    run_id: UUID
    resource: str
    window_start: date
    window_end_exclusive: date

    record_count: int
    data_file: str
    sha256: str

    created_at: datetime

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported manifest schema version")

        if not self.resource.strip():
            raise ValueError("Resource must not be empty")

        if self.window_end_exclusive - self.window_start != timedelta(days=1):
            raise ValueError("Ingestion window must cover exactly one day")

        if self.record_count < 0:
            raise ValueError("Record count must be non-negative")

        path = PurePosixPath(self.data_file)

        if (
            not self.data_file.strip()
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in self.data_file
        ):
            raise ValueError("Invalid data file path")

        if re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256) is None:
            raise ValueError("Invalid SHA-256 checksum")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
