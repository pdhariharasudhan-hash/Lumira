from app.services.planner.step_result import (
    StepResult
)


class PlanExecutorV2:

    def __init__(
        self
    ):

        self.handlers = {

            "validate":
            self._validate,

            "builder":
            self._builder,

            "execute":
            self._execute,

            "code":
            self._code,

            "save_project":
            self._save_project,

            "generate_image":
            self._generate_image,

            "save_artifact":
            self._save_artifact,

            "capture_audio":
            self._capture_audio,

            "transcribe":
            self._transcribe,

            "summarize":
            self._summarize
        }

    def execute(
        self,
        plan: dict
    ):

        results = []

        for step in plan.get(
            "steps",
            []
        ):

            handler = (
                self.handlers.get(
                    step
                )
            )

            if not handler:

                results.append(

                    StepResult(
                        step,
                        False,
                        {
                            "error":
                            "handler not found"
                        }
                    ).to_dict()

                )

                continue

            result = handler()

            results.append(
                result.to_dict()
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

            "results":
            results
        }

    def _validate(
        self
    ):

        return StepResult(
            "validate",
            True
        )

    def _builder(
        self
    ):

        return StepResult(
            "builder",
            True
        )

    def _execute(
        self
    ):

        return StepResult(
            "execute",
            True
        )

    def _code(
        self
    ):

        return StepResult(
            "code",
            True
        )

    def _save_project(
        self
    ):

        return StepResult(
            "save_project",
            True
        )

    def _generate_image(
        self
    ):

        return StepResult(
            "generate_image",
            True
        )

    def _save_artifact(
        self
    ):

        return StepResult(
            "save_artifact",
            True
        )

    def _capture_audio(
        self
    ):

        return StepResult(
            "capture_audio",
            True
        )

    def _transcribe(
        self
    ):

        return StepResult(
            "transcribe",
            True
        )

    def _summarize(
        self
    ):

        return StepResult(
            "summarize",
            True
        )