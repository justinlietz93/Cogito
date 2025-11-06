"""Shared timeout helpers for infrastructure-level integrations.

Purpose:
    Offer reusable utilities for retrieving timeout configuration and
    enforcing execution limits around blocking operations. The module keeps
    timeout policies centralised so adapters can honour user preferences while
    remaining framework-agnostic.
External Dependencies:
    Python standard library only (``contextlib``, ``dataclasses``, ``signal``,
    and ``threading``).
Fallback Semantics:
    When timeout values are absent the helpers degrade gracefully by yielding
    without enforcing limits, ensuring existing code paths continue to work.
Timeout Strategy:
    Implements wall-clock timeouts using ``signal.setitimer`` on the main
    thread. When signals are unavailable the context manager becomes a no-op.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import signal
import threading
from typing import Any, Generator, Mapping, Optional


@dataclass(frozen=True)
class TimeoutConfig:
    """Structured timeout configuration for blocking operations.

    Attributes:
        total_seconds: Optional overall timeout applied to the wrapped
            operation. When ``None`` or non-positive, the timeout is disabled.
        start_timeout_seconds: Optional timeout for initial response or
            handshake phases. The current implementation does not enforce this
            value but records it for future streaming integrations.
    """

    total_seconds: Optional[float] = None
    start_timeout_seconds: Optional[float] = None


def _follow_scope(mapping: Mapping[str, Any], scope: str) -> Mapping[str, Any]:
    """Return the nested mapping referenced by ``scope`` within ``mapping``."""

    current: Mapping[str, Any] = mapping
    for part in scope.split("."):
        candidate = current.get(part, {}) if isinstance(current, Mapping) else {}
        if not isinstance(candidate, Mapping):
            return {}
        current = candidate
    return current


def _coerce_optional_float(value: Any) -> Optional[float]:
    """Convert ``value`` to ``float`` when possible."""

    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def get_timeout_config(
    config: Optional[Mapping[str, Any]],
    *,
    scope: str,
    default_total_seconds: Optional[float] = None,
) -> TimeoutConfig:
    """Extract timeout settings for the specified ``scope``.

    Args:
        config: Optional configuration mapping that may contain a ``timeouts``
            section describing per-scope limits.
        scope: Dot-delimited path resolving to the desired timeout settings
            (for example ``"preflight.extraction"``).
        default_total_seconds: Optional fallback total timeout applied when the
            configuration omits an explicit value.

    Returns:
        :class:`TimeoutConfig` populated with the resolved timeout values. When
        no values are configured the defaults are returned.

    Raises:
        None. Invalid or missing configuration entries are treated as absent
        values.

    Side Effects:
        None. The function only inspects the provided mapping.

    Timeout:
        Not applicable; execution performs deterministic mapping lookups.
    """

    config_map: Mapping[str, Any] = config or {}
    timeouts_section = config_map.get("timeouts", {})
    if not isinstance(timeouts_section, Mapping):
        timeouts_section = {}

    scoped = _follow_scope(timeouts_section, scope)
    total = _coerce_optional_float(scoped.get("total_seconds"))
    start = _coerce_optional_float(scoped.get("start_seconds"))

    if total is None:
        total = _coerce_optional_float(default_total_seconds)

    return TimeoutConfig(total_seconds=total, start_timeout_seconds=start)


@contextmanager
def operation_timeout(config: TimeoutConfig, *, operation: str) -> Generator[None, None, None]:
    """Enforce the supplied timeout around a blocking operation.

    Args:
        config: Timeout parameters retrieved via :func:`get_timeout_config`.
        operation: Human-readable operation name included in timeout errors.

    Yields:
        ``None`` while the wrapped block executes.

    Raises:
        TimeoutError: When the operation exceeds ``config.total_seconds``.

    Side Effects:
        Installs a temporary signal handler when the timeout is active.

    Timeout:
        Managed internally using :func:`signal.setitimer` on the main thread.
    """

    total_seconds = config.total_seconds
    if total_seconds is None:
        yield
        return

    if threading.current_thread() is not threading.main_thread():
        # Signal-based timers only work reliably on the main thread; degrade to no-op.
        yield
        return

    def _timeout_handler(_: int, __: Optional[object]) -> None:
        raise TimeoutError(
            f"Operation '{operation}' exceeded timeout of {total_seconds} seconds."
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, total_seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


__all__ = ["TimeoutConfig", "get_timeout_config", "operation_timeout"]
