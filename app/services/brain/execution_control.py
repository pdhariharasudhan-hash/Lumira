"""Cooperative execution budgets and cancellation for one Brain run."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, RLock
from time import monotonic


class BrainExecutionInterrupted(RuntimeError):
    """A Brain run reached its deadline or received cancellation."""

    def __init__(self, status: str) -> None:
        if status not in {"cancelled", "timed_out"}:
            raise ValueError("unsupported interruption status")
        self.status = status
        super().__init__(
            "Brain execution was cancelled."
            if status == "cancelled"
            else "Brain execution exceeded its time budget."
        )


@dataclass
class BrainExecutionControl:
    execution_id: str
    session_id: str
    deadline: float
    _cancel_event: Event = field(default_factory=Event, repr=False)

    def cancel(self) -> None:
        self._cancel_event.set()

    def check(self) -> None:
        if self._cancel_event.is_set():
            raise BrainExecutionInterrupted("cancelled")
        if monotonic() >= self.deadline:
            raise BrainExecutionInterrupted("timed_out")


class BrainExecutionControlRegistry:
    """In-process control registry; cancellation is cooperative between stages."""

    DEFAULT_TIMEOUT_SECONDS = 120.0
    MAX_TIMEOUT_SECONDS = 600.0
    _lock = RLock()
    _active: dict[str, BrainExecutionControl] = {}
    _by_session: dict[str, set[str]] = {}

    @classmethod
    def register(
        cls,
        execution_id: str,
        session_id: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> BrainExecutionControl:
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise ValueError("execution_id is required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id is required")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be numeric")
        if not 0 < float(timeout_seconds) <= cls.MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds is outside the allowed range")

        control = BrainExecutionControl(
            execution_id=execution_id,
            session_id=session_id,
            deadline=monotonic() + float(timeout_seconds),
        )
        with cls._lock:
            if execution_id in cls._active:
                raise ValueError("execution_id is already active")
            cls._active[execution_id] = control
            cls._by_session.setdefault(session_id, set()).add(execution_id)
        return control

    @classmethod
    def cancel_for_session(cls, session_id: str) -> int:
        if not isinstance(session_id, str) or not session_id.strip():
            return 0
        with cls._lock:
            execution_ids = tuple(cls._by_session.get(session_id, ()))
            controls = [cls._active[item] for item in execution_ids if item in cls._active]
            for control in controls:
                control.cancel()
            return len(controls)

    @classmethod
    def release(cls, execution_id: str) -> None:
        with cls._lock:
            control = cls._active.pop(execution_id, None)
            if control is None:
                return
            session_runs = cls._by_session.get(control.session_id)
            if session_runs is not None:
                session_runs.discard(execution_id)
                if not session_runs:
                    cls._by_session.pop(control.session_id, None)

    @classmethod
    def active_count(cls) -> int:
        with cls._lock:
            return len(cls._active)
