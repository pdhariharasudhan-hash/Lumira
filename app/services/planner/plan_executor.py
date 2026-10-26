class PlanExecutor:

    def execute(
        self,
        plan: dict
    ):

        executed_steps = []

        for step in plan.get(
            "steps",
            []
        ):

            executed_steps.append(
                step
            )

        return {

            "success":
            True,

            "goal":
            plan.get(
                "goal"
            ),

            "intent":
            plan.get(
                "intent"
            ),

            "executed_steps":
            executed_steps,

            "total_steps":
            len(
                executed_steps
            )
        }