from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class IngestionWindow:
    resource: str
    start_date: date
    end_date_exclusive: date

    def __post_init__(self):
        if not self.resource.strip():
            raise ValueError("Resource must not be empty.")

        if self.start_date >= self.end_date_exclusive:
            raise ValueError("Start date must be before end date exclusive.")

        if self.end_date_exclusive - self.start_date != timedelta(days=1):
            raise ValueError("IngestionWindow must cover exactly one day")
