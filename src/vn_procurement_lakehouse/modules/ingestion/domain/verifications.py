from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    INVALID = "INVALID"


@dataclass(frozen=True)
class VerificationResult:
    run_id: UUID
    status: VerificationStatus
    reason: str | None = None
    record_count: int | None = None
