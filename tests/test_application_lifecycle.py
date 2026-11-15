import asyncio

import pytest

from app.services.system.application_lifecycle_service import (
    ApplicationLifecycleManager,
    LifecycleError,
)


async def _ordered_startup_and_reverse_shutdown():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("late", lambda: events.append("start-late"), lambda: events.append("stop-late"), priority=20)
    manager.register("early", lambda: events.append("start-early"), lambda: events.append("stop-early"), priority=10)
    await manager.startup()
    assert manager.state == "running"
    await manager.shutdown()
    assert manager.state == "stopped"
    assert events == ["start-early", "start-late", "stop-late", "stop-early"]


def test_startup_is_ordered_and_shutdown_is_reverse_order():
    asyncio.run(_ordered_startup_and_reverse_shutdown())


async def _async_hooks():
    events = []
    async def start():
        events.append("start")
    async def stop():
        events.append("stop")
    manager = ApplicationLifecycleManager()
    manager.register("async", start, stop)
    await manager.startup()
    await manager.shutdown()
    assert events == ["start", "stop"]


def test_async_hooks_are_supported():
    asyncio.run(_async_hooks())


async def _startup_idempotency():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("once", lambda: events.append("start"))
    await manager.startup()
    await manager.startup()
    assert events == ["start"]


def test_startup_is_idempotent_while_running():
    asyncio.run(_startup_idempotency())


async def _partial_startup_rollback():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("one", lambda: events.append("start-one"), lambda: events.append("stop-one"), priority=1)
    def fail():
        events.append("start-two")
        raise RuntimeError("private failure detail")
    manager.register("two", fail, priority=2)
    with pytest.raises(LifecycleError, match="startup failed at hook two"):
        await manager.startup()
    assert manager.state == "failed"
    assert events == ["start-one", "start-two", "stop-one"]


def test_partial_startup_failure_rolls_back_started_hooks():
    asyncio.run(_partial_startup_rollback())


async def _shutdown_attempts_all_hooks():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("one", lambda: None, lambda: (_ for _ in ()).throw(RuntimeError("secret")))
    manager.register("two", lambda: None, lambda: events.append("stop-two"))
    await manager.startup()
    with pytest.raises(LifecycleError, match="one:RuntimeError"):
        await manager.shutdown()
    assert manager.state == "stopped"
    assert events == ["stop-two"]


def test_shutdown_attempts_all_hooks_and_reports_safe_error_types():
    asyncio.run(_shutdown_attempts_all_hooks())


async def _restart_after_shutdown():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("reusable", lambda: events.append("start"), lambda: events.append("stop"))
    await manager.startup()
    await manager.shutdown()
    await manager.startup()
    await manager.shutdown()
    assert events == ["start", "stop", "start", "stop"]


def test_manager_can_restart_after_clean_shutdown():
    asyncio.run(_restart_after_shutdown())


def test_registration_validates_names_callbacks_and_duplicates():
    manager = ApplicationLifecycleManager()
    with pytest.raises(ValueError):
        manager.register(" ", lambda: None)
    with pytest.raises(TypeError):
        manager.register("bad", None)
    manager.register("good", lambda: None)
    with pytest.raises(ValueError, match="already registered"):
        manager.register("good", lambda: None)


async def _registration_after_startup_rejected():
    manager = ApplicationLifecycleManager()
    manager.register("one", lambda: None)
    await manager.startup()
    with pytest.raises(LifecycleError, match="before startup"):
        manager.register("two", lambda: None)


def test_hooks_cannot_be_registered_after_startup():
    asyncio.run(_registration_after_startup_rejected())


def test_snapshot_reports_safe_lifecycle_metadata():
    manager = ApplicationLifecycleManager()
    manager.register("one", lambda: None, priority=2)
    manager.register("two", lambda: None, priority=1)
    assert manager.snapshot() == {
        "state": "new",
        "registered_hooks": ["two", "one"],
        "started_hooks": [],
        "active_work": 0,
    }


async def _shutdown_drains_inflight_work():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("resource", lambda: None, lambda: events.append("closed"))
    await manager.startup()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def work():
        async with manager.track_work():
            entered.set()
            await release.wait()

    task = asyncio.create_task(work())
    await entered.wait()
    shutdown = asyncio.create_task(manager.shutdown(timeout_seconds=1))
    await asyncio.sleep(0)
    assert manager.state == "stopping"
    assert events == []
    release.set()
    await task
    await shutdown
    assert events == ["closed"]
    assert manager.snapshot()["active_work"] == 0


def test_shutdown_drains_inflight_work_before_cleanup():
    asyncio.run(_shutdown_drains_inflight_work())


async def _shutdown_timeout_can_be_retried():
    manager = ApplicationLifecycleManager()
    await manager.startup()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def work():
        async with manager.track_work():
            entered.set()
            await release.wait()

    task = asyncio.create_task(work())
    await entered.wait()
    with pytest.raises(LifecycleError, match="timed out"):
        await manager.shutdown(timeout_seconds=0.01)
    assert manager.state == "stopping"
    release.set()
    await task
    await manager.shutdown(timeout_seconds=1)
    assert manager.state == "stopped"


def test_shutdown_timeout_keeps_manager_stopping_until_retry():
    asyncio.run(_shutdown_timeout_can_be_retried())


async def _explicit_restart():
    events = []
    manager = ApplicationLifecycleManager()
    manager.register("resource", lambda: events.append("start"), lambda: events.append("stop"))
    await manager.startup()
    await manager.restart(timeout_seconds=1)
    await manager.shutdown(timeout_seconds=1)
    assert events == ["start", "stop", "start", "stop"]


def test_explicit_restart_runs_clean_lifecycle_again():
    asyncio.run(_explicit_restart())
