from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DayCoverage:
    date: date
    status: str
    record_count: int | None
    run_id: UUID | None
    storage_uri: str | None
