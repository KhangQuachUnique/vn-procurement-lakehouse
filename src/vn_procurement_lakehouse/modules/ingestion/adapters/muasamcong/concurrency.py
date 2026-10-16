from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def iter_concurrent_details[T, R](
    items: list[T],
    fetch_fn: Callable[[T], R],
    *,
    max_workers: int = 3,
) -> Iterator[R]:
    """Fetch details for a list of search items concurrently using bounded thread execution.

    Bounds the number of submitted futures in memory at any time to `min(max_workers, len(items))`
    and yields results as they complete.
    """
    if not items:
        return

    if max_workers <= 1 or len(items) <= 1:
        for item in items:
            yield fetch_fn(item)
        return

    worker_count = min(max_workers, len(items))
    remaining = iter(items)

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="msc-detail") as pool:
        pending: set[Future[R]] = {
            pool.submit(fetch_fn, item) for item in [next(remaining) for _ in range(worker_count)]
        }

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                next_item = next(remaining, None)
                if next_item is not None:
                    pending.add(pool.submit(fetch_fn, next_item))
