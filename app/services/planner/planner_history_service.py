from pathlib import Path
from datetime import datetime
import json

from app.services.history.event_logger_service import (
    EventLoggerService
)


class PlannerHistoryService:

    def __init__(self):

        self.history_file = Path(
            "memory/planner_history.json"
        )

        self.history_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.history_file.exists():

            self._write(
                []
            )

    def _read(
        self
    ):

        content = (
            self.history_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return []

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.history_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def add_plan(
        self,
        plan: dict
    ):

        history = (
            self._read()
        )

        record = {

            "goal":
            plan.get(
                "goal"
            ),

            "intent":
            plan.get(
                "intent"
            ),

            "steps":
            plan.get(
                "steps",
                []
            ),

            "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        history.append(
            record
        )

        self._write(
            history
        )

        EventLoggerService().log(
            event="plan_created",
            source="planner",
            data={

                "goal":
                record[
                    "goal"
                ],

                "intent":
                record[
                    "intent"
                ],

                "step_count":
                len(
                    record[
                        "steps"
                    ]
                )
            }
        )

        return {

            "success":
            True
        }

    def get_history(
        self
    ):

        return self._read()

    def latest(
        self
    ):

        history = (
            self._read()
        )

        if not history:

            return None

        return history[-1]

    def clear(
        self
    ):

        self._write(
            []
        )

        EventLoggerService().log(
            event="planner_history_cleared",
            source="planner",
            data={}
        )

        return {

            "success":
            True
        }

    def count(
        self
    ):

        return len(
            self._read()
        )