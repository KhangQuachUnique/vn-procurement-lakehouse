import time

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.concurrency import (
    iter_concurrent_details,
)


def test_iter_concurrent_details_empty() -> None:
    results = list(iter_concurrent_details([], lambda x: x))
    assert results == []


def test_iter_concurrent_details_single_worker() -> None:
    items = [1, 2, 3]
    results = list(iter_concurrent_details(items, lambda x: x * 2, max_workers=1))
    assert results == [2, 4, 6]


def test_iter_concurrent_details_multi_worker() -> None:
    items = list(range(10))

    def fetch(x: int) -> int:
        time.sleep(0.01)
        return x * 10

    results = list(iter_concurrent_details(items, fetch, max_workers=4))
    # All items returned (order may vary due to concurrency)
    assert sorted(results) == [x * 10 for x in items]


def test_iter_concurrent_details_propagates_exception() -> None:
    items = [1, 2, 3, 4]

    def fail_on_three(x: int) -> int:
        if x == 3:
            raise RuntimeError("Fetch failed for item 3")
        return x

    with pytest.raises(RuntimeError, match="Fetch failed for item 3"):
        list(iter_concurrent_details(items, fail_on_three, max_workers=2))
