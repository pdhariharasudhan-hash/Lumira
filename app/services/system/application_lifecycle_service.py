"""Ordered async lifecycle orchestration with rollback and graceful shutdown."""
from __future__ import annotations

import asyncio
import inspect
import math
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable


class LifecycleError(RuntimeError):
    """Raised when lifecycle startup or shutdown cannot complete cleanly."""


@dataclass(frozen=True)
class LifecycleHook:
    name: str
    startup: Callable[[], Any]
    shutdown: Callable[[], Any] | None = None
    priority: int = 100


class ApplicationLifecycleManager:
    """Run startup hooks in priority order and shutdown hooks in reverse order."""

    STATES = frozenset({"new", "starting", "running", "stopping", "stopped", "failed"})

    def __init__(self) -> None:
        self._hooks: dict[str, LifecycleHook] = {}
        self._started: list[LifecycleHook] = []
        self._state = "new"
        self._lock = asyncio.Lock()
        self._work_condition = asyncio.Condition()
        self._active_work = 0

    @property
    def state(self) -> str:
        return self._state

    def register(
        self,
        name: str,
        startup: Callable[[], Any],
        shutdown: Callable[[], Any] | None = None,
        *,
        priority: int = 100,
    ) -> None:
        if self._state not in {"new", "stopped"}:
            raise LifecycleError("hooks can only be registered before startup")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("hook name must be a non-empty string")
        if not callable(startup) or (shutdown is not None and not callable(shutdown)):
            raise TypeError("lifecycle hooks must be callable")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError("hook priority must be an integer")
        normalized = name.strip()
        if normalized in self._hooks:
            raise ValueError(f"lifecycle hook already registered: {normalized}")
        self._hooks[normalized] = LifecycleHook(normalized, startup, shutdown, priority)

    @staticmethod
    async def _invoke(callback: Callable[[], Any]) -> Any:
        result = callback()
        if inspect.isawaitable(result):
            return await result
        return result

    async def startup(self) -> None:
        async with self._lock:
            if self._state == "running":
                return
            if self._state in {"starting", "stopping"}:
                raise LifecycleError(f"cannot start while lifecycle is {self._state}")
            self._state = "starting"
            self._started = []
            ordered = sorted(self._hooks.values(), key=lambda hook: (hook.priority, hook.name))
            try:
                for hook in ordered:
                    await self._invoke(hook.startup)
                    self._started.append(hook)
            except Exception as exc:
                rollback_errors = []
                for started in reversed(self._started):
                    if started.shutdown is None:
                        continue
                    try:
                        await self._invoke(started.shutdown)
                    except Exception as rollback_exc:
                        rollback_errors.append(type(rollback_exc).__name__)
                self._started = []
                self._state = "failed"
                suffix = (
                    f"; rollback errors: {', '.join(rollback_errors)}"
                    if rollback_errors else ""
                )
                raise LifecycleError(
                    f"startup failed at hook {hook.name} ({type(exc).__name__}){suffix}"
                ) from exc
            self._state = "running"

    @asynccontextmanager
    async def track_work(self):
        """Track in-flight work so shutdown can drain before releasing resources."""
        async with self._work_condition:
            if self._state != "running":
                raise LifecycleError("application is not accepting new work")
            self._active_work += 1
        try:
            yield
        finally:
            async with self._work_condition:
                self._active_work -= 1
                self._work_condition.notify_all()

    async def _wait_for_work_to_drain(self) -> None:
        async with self._work_condition:
            await self._work_condition.wait_for(lambda: self._active_work == 0)

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be a finite positive number")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        async with self._lock:
            if self._state in {"new", "stopped"}:
                self._state = "stopped"
                return
            if self._state not in {"running", "failed", "stopping"}:
                raise LifecycleError(f"cannot shut down while lifecycle is {self._state}")
            self._state = "stopping"
            try:
                await asyncio.wait_for(
                    self._wait_for_work_to_drain(), timeout=float(timeout_seconds)
                )
            except asyncio.TimeoutError as exc:
                # Keep the manager in stopping state; callers may retry shutdown.
                raise LifecycleError("shutdown timed out waiting for in-flight work") from exc

            errors = []
            for hook in reversed(self._started):
                if hook.shutdown is None:
                    continue
                try:
                    await self._invoke(hook.shutdown)
                except Exception as exc:
                    errors.append(f"{hook.name}:{type(exc).__name__}")
            self._started = []
            self._state = "stopped"
            if errors:
                raise LifecycleError(
                    "shutdown completed with hook errors: " + ", ".join(errors)
                )

    async def restart(self, timeout_seconds: float = 30.0) -> None:
        """Drain and shut down the current lifecycle before starting it again."""
        await self.shutdown(timeout_seconds=timeout_seconds)
        await self.startup()

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self._state,
            "registered_hooks": [
                hook.name for hook in sorted(
                    self._hooks.values(), key=lambda item: (item.priority, item.name)
                )
            ],
            "started_hooks": [hook.name for hook in self._started],
            "active_work": self._active_work,
        }
