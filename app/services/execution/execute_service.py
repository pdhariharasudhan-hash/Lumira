#execute_service.py

from typing import Dict, Any


class ExecuteService:

    def execute(
        self,
        idea: str,
        builder: Dict[str, Any]
    ) -> Dict[str, Any]:

        steps = builder[
            "suggested_steps"
        ]

        execution_order = []

        for step in steps:

            execution_order.append(
                step["id"]
            )

        if len(
            execution_order
        ) == 0:

            return {

                "execution_order": [],

                "today_task": None,

                "task_steps": [],

                "expected_output":
                "nothing generated",

                "blockers": [
                    "no steps created"
                ],

                "status":
                "reject"
            }

        return {

            "execution_order":
            execution_order,

            "today_task":
            execution_order[-1],

            "task_steps":
            execution_order,

            "expected_output":
            steps[-1][
                "expected_output"
            ],

            "blockers": [],

            "status":
            "accept"
        }