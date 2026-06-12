from datetime import datetime


class StepResult:

    def __init__(
        self,
        step: str,
        success: bool,
        output=None
    ):

        self.step = step

        self.success = success

        self.output = (
            output
            if output is not None
            else {}
        )

        self.timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    def to_dict(
        self
    ):

        return {

            "step":
            self.step,

            "success":
            self.success,

            "output":
            self.output,

            "timestamp":
            self.timestamp
        }