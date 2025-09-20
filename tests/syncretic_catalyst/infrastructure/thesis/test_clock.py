from datetime import datetime

def test_system_clock_returns_datetime() -> None:
    from syncretic_catalyst.infrastructure.thesis.clock import SystemClock

    clock = SystemClock()
    now = clock.now()

    assert isinstance(now, datetime)
