from datetime import date

import pytest

from vn_procurement_lakehouse.modules.ingestion.domain.window import IngestionWindow


def test_valid_window() -> None:
    window = IngestionWindow(
        resource="tbmt",
        start_date=date(2026, 6, 19),
        end_date_exclusive=date(2026, 6, 20),
    )

    assert window.resource == "tbmt"
    assert window.start_date == date(2026, 6, 19)
    assert window.end_date_exclusive == date(2026, 6, 20)


def test_empty_resource() -> None:
    with pytest.raises(ValueError, match="Resource must not be empty."):
        IngestionWindow(
            resource="   ",
            start_date=date(2026, 6, 19),
            end_date_exclusive=date(2026, 6, 20),
        )


def test_invalid_date_range() -> None:
    with pytest.raises(ValueError, match="Start date must be before end date"):
        IngestionWindow(
            resource="tbmt",
            start_date=date(2026, 6, 20),
            end_date_exclusive=date(2026, 6, 19),
        )


def test_equal_date_range() -> None:
    with pytest.raises(ValueError, match="Start date must be before end date"):
        IngestionWindow(
            resource="tbmt",
            start_date=date(2026, 6, 20),
            end_date_exclusive=date(2026, 6, 20),
        )
