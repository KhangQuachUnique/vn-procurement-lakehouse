from datetime import date
from unittest.mock import MagicMock

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.composite_source import (
    CompositeSource,
    normalize_resource_name,
)
from vn_procurement_lakehouse.modules.ingestion.application.ports import SourcePort
from vn_procurement_lakehouse.modules.ingestion.domain.models import IngestionWindow


@pytest.fixture
def project_window() -> IngestionWindow:
    return IngestionWindow(
        resource="project",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )


def test_composite_source_conforms_to_source_port() -> None:
    composite = CompositeSource(sources={})
    source_port: SourcePort = composite
    assert hasattr(source_port, "fetch")
    assert callable(source_port.fetch)


def test_composite_source_routes_to_matching_source(project_window: IngestionWindow) -> None:
    mock_project_source = MagicMock(spec=SourcePort)
    mock_project_source.fetch.return_value = iter([{"id": "PRJ001"}])

    mock_khlcnt_source = MagicMock(spec=SourcePort)

    composite = CompositeSource(
        sources={
            "project": mock_project_source,
            "khlcnt": mock_khlcnt_source,
        }
    )

    records = list(composite.fetch(project_window))
    assert records == [{"id": "PRJ001"}]
    mock_project_source.fetch.assert_called_once_with(project_window)
    mock_khlcnt_source.fetch.assert_not_called()


def test_composite_source_normalizes_alias(project_window: IngestionWindow) -> None:
    mock_khlcnt_source = MagicMock(spec=SourcePort)
    mock_khlcnt_source.fetch.return_value = iter([{"id": "PLAN001"}])

    composite = CompositeSource(sources={"khlcnt": mock_khlcnt_source})

    # Call with alias "plan"
    plan_window = IngestionWindow(
        resource="plan",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    records = list(composite.fetch(plan_window))
    assert records == [{"id": "PLAN001"}]

    # Should have normalized resource to "khlcnt" in the window passed to the underlying source
    call_arg = mock_khlcnt_source.fetch.call_args[0][0]
    assert isinstance(call_arg, IngestionWindow)
    assert call_arg.resource == "khlcnt"


def test_composite_source_unsupported_resource_raises_eagerly(
    project_window: IngestionWindow,
) -> None:
    composite = CompositeSource(sources={"project": MagicMock()})

    window = IngestionWindow(
        resource="unknown_res",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    with pytest.raises(ValueError, match="Unsupported resource 'unknown_res'"):
        composite.fetch(window)


@pytest.mark.parametrize(
    "alias, canonical",
    [
        ("project", "project"),
        ("khlcnt", "khlcnt"),
        ("plan", "khlcnt"),
        ("tbmt", "tbmt"),
        ("notify_contractor", "tbmt"),
        ("kqlcnt", "kqlcnt"),
        ("contractor_result", "kqlcnt"),
        ("bid_opening", "bid_opening"),
        ("bbmt", "bid_opening"),
        ("PROJECT", "project"),
        ("  KHLCNT  ", "khlcnt"),
    ],
)
def test_normalize_resource_name(alias: str, canonical: str) -> None:
    assert normalize_resource_name(alias) == canonical
