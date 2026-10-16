import threading
import time

import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.budget import (
    RequestBudget,
)


def test_invalid_parameters() -> None:
    with pytest.raises(ValueError, match="max_inflight must be positive"):
        RequestBudget(max_inflight=0)

    with pytest.raises(ValueError, match="min_interval must be finite and non-negative"):
        RequestBudget(min_interval=-0.1)

    with pytest.raises(ValueError, match="min_interval must be finite and non-negative"):
        RequestBudget(min_interval=float("inf"))

    with pytest.raises(ValueError, match="min_interval must be finite and non-negative"):
        RequestBudget(min_interval=float("nan"))


def test_request_budget_limits_concurrent_inflight() -> None:
    budget = RequestBudget(max_inflight=2, min_interval=0.0)
    current_active = 0
    max_observed = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal current_active, max_observed
        with budget.request():
            with lock:
                current_active += 1
                if current_active > max_observed:
                    max_observed = current_active
            time.sleep(0.05)
            with lock:
                current_active -= 1

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Không bao giờ vượt quá 2 connection cùng lúc
    assert max_observed <= 2


def test_request_budget_defer_pauses_all_workers() -> None:
    current_time = 100.0
    waited_total = 0.0

    def fake_clock() -> float:
        return current_time

    def fake_wait(delay: float) -> None:
        nonlocal current_time, waited_total
        waited_total += delay
        current_time += delay

    budget = RequestBudget(
        max_inflight=3, min_interval=0.0, clock=fake_clock, wait=fake_wait
    )

    # Đóng băng 5 giây
    budget.defer(5.0)

    with budget.request():
        pass

    assert waited_total >= 5.0


def test_defer_with_zero_or_negative_seconds_ignored() -> None:
    current_time = 100.0

    def fake_clock() -> float:
        return current_time

    budget = RequestBudget(max_inflight=3, min_interval=0.0, clock=fake_clock)
    budget.defer(0.0)
    budget.defer(-5.0)

    # Cooldown không bị thay đổi
    assert budget._cooldown_until == 0.0


def test_request_budget_pacing() -> None:
    current_time = 100.0
    waited_total = 0.0

    def fake_clock() -> float:
        return current_time

    def fake_wait(delay: float) -> None:
        nonlocal current_time, waited_total
        waited_total += delay
        current_time += delay

    budget = RequestBudget(
        max_inflight=3, min_interval=0.1, clock=fake_clock, wait=fake_wait
    )

    # Lần 1: Không phải chờ
    with budget.request():
        pass
    assert waited_total == 0.0

    # Lần 2 ngay lập tức: phải chờ min_interval (0.1s)
    with budget.request():
        pass
    assert waited_total == pytest.approx(0.1)

