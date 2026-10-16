from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PublishedBatch:
    run_id: UUID
    record_count: int
    storage_uri: str
