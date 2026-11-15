from datetime import datetime
from pathlib import Path

from app.services.history.event_logger_service import EventLoggerService
from app.services.persistence.atomic_json_store import (
    AtomicJsonStore,
    PersistenceIntegrityError,
)


class PlannerHistoryService:
    def __init__(self):
        self.history_file = Path("memory/planner_history.json")
        self.store = AtomicJsonStore(self.history_file)

    @staticmethod
    def _validate_history(history):
        if not isinstance(history, list):
            raise PersistenceIntegrityError("Planner history must be a list")
        if any(not isinstance(record, dict) for record in history):
            raise PersistenceIntegrityError("Planner history contains an invalid record")
        return history

    def _read(self):
        return self._validate_history(self.store.read([]))

    def _write(self, data):
        self.store.write(self._validate_history(data))

    def add_plan(self, plan: dict):
        if not isinstance(plan, dict):
            raise ValueError("plan must be a dictionary")
        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("plan steps must be a list")

        record = {
            "goal": plan.get("goal"),
            "intent": plan.get("intent"),
            "steps": steps,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        def append(history):
            self._validate_history(history)
            history.append(record)

        self.store.update(append, [])

        EventLoggerService().log(
            event="plan_created",
            source="planner",
            data={
                "goal": record["goal"],
                "intent": record["intent"],
                "step_count": len(record["steps"]),
            },
        )

        return {"success": True}

    def get_history(self):
        return self._read()

    def latest(self):
        history = self._read()
        if not history:
            return None
        return history[-1]

    def clear(self):
        self._write([])
        EventLoggerService().log(
            event="planner_history_cleared",
            source="planner",
            data={},
        )
        return {"success": True}

    def count(self):
        return len(self._read())
