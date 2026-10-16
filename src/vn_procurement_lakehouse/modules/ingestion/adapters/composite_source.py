from collections.abc import Iterator
from typing import Any

from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow

RawPayload = dict[str, Any]

# Resource aliases mapping friendly names to canonical resource names
RESOURCE_ALIASES: dict[str, str] = {
    "project": "project",
    "khlcnt": "khlcnt",
    "plan": "khlcnt",
    "tbmt": "tbmt",
    "notify_contractor": "tbmt",
    "kqlcnt": "kqlcnt",
    "contractor_result": "kqlcnt",
    "bid_opening": "bid_opening",
    "bbmt": "bid_opening",
}


def normalize_resource_name(resource: str) -> str:
    cleaned = resource.strip().lower()
    return RESOURCE_ALIASES.get(cleaned, cleaned)


class CompositeSource:
    """Multi-resource SourcePort adapter routing fetch requests to resource-specific sources."""

    def __init__(self, sources: dict[str, SourcePort]) -> None:
        self._sources = sources

    def fetch(self, ingestion_window: IngestionWindow) -> Iterator[RawPayload]:
        canonical_resource = normalize_resource_name(ingestion_window.resource)
        source = self._sources.get(canonical_resource)

        if not source:
            supported = ", ".join(sorted(self._sources.keys()))
            raise ValueError(
                f"Unsupported resource '{ingestion_window.resource}'. Supported resources: {supported}"
            )

        # Normalize the window resource to the canonical name if needed
        if ingestion_window.resource != canonical_resource:
            normalized_window = IngestionWindow(
                resource=canonical_resource,
                start_date=ingestion_window.start_date,
                end_date_exclusive=ingestion_window.end_date_exclusive,
            )
            return source.fetch(normalized_window)

        return source.fetch(ingestion_window)
