"""Clock implementations for the thesis builder."""
from __future__ import annotations

from datetime import datetime


class SystemClock:
    """Uses :func:`datetime.now` to provide timestamps."""

    def now(self) -> datetime:
        return datetime.now()
