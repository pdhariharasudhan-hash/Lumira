from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from app.services.history.event_logger_service import EventLoggerService
from app.services.persistence.atomic_json_store import PersistenceIntegrityError
from app.services.planner.planner_history_service import PlannerHistoryService


def test_corrupt_planner_history_is_rejected_without_rewriting_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("memory/planner_history.json")
    path.parent.mkdir(parents=True)
    original = b"{not-json"
    path.write_bytes(original)
    service = PlannerHistoryService()

    with pytest.raises(PersistenceIntegrityError):
        service.get_history()

    assert path.read_bytes() == original


def test_invalid_planner_history_shape_is_rejected_without_rewriting_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = Path("memory/planner_history.json")
    path.parent.mkdir(parents=True)
    original = b'{"unexpected": true}'
    path.write_bytes(original)
    service = PlannerHistoryService()

    with pytest.raises(PersistenceIntegrityError):
        service.get_history()

    assert path.read_bytes() == original


def test_concurrent_plan_writes_do_not_lose_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EventLoggerService, "log", lambda *args, **kwargs: None)
    services = [PlannerHistoryService(), PlannerHistoryService()]
    barrier = Barrier(2)
    for service in services:
        original_read = service._read

        def synchronized_read(read=original_read):
            history = read()
            barrier.wait(timeout=5)
            return history

        monkeypatch.setattr(service, "_read", synchronized_read)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(service.add_plan, {"goal": goal, "intent": "test", "steps": []})
            for service, goal in zip(services, ("first", "second"))
        ]
        for future in futures:
            future.result(timeout=10)

    history = PlannerHistoryService().get_history()
    assert {record["goal"] for record in history} == {"first", "second"}
