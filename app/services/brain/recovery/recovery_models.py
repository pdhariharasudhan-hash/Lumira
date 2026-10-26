from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional


@dataclass
class FailureRecord:
    stage: str
    order: int
    error: str
    retry_count: int = 0
    recovered: bool = False
    aborted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "order": self.order,
            "error": self.error,
            "retry_count": self.retry_count,
            "recovered": self.recovered,
            "aborted": self.aborted,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "FailureRecord":
        if not isinstance(data, dict):
            raise TypeError(
                "failure record must be a dictionary"
            )

        required = {
            "stage",
            "order",
            "error",
            "retry_count",
            "recovered",
            "aborted",
        }

        if set(data.keys()) != required:
            raise ValueError(
                "invalid failure record fields"
            )

        if not isinstance(data["stage"], str):
            raise TypeError(
                "failure stage must be a string"
            )

        if not isinstance(data["order"], int) or isinstance(
            data["order"],
            bool,
        ):
            raise TypeError(
                "failure order must be an integer"
            )

        if not isinstance(data["error"], str):
            raise TypeError(
                "failure error must be a string"
            )

        if not isinstance(data["retry_count"], int) or isinstance(
            data["retry_count"],
            bool,
        ):
            raise TypeError(
                "failure retry_count must be an integer"
            )

        if data["retry_count"] < 0:
            raise ValueError(
                "failure retry_count must not be negative"
            )

        if not isinstance(data["recovered"], bool):
            raise TypeError(
                "failure recovered must be boolean"
            )

        if not isinstance(data["aborted"], bool):
            raise TypeError(
                "failure aborted must be boolean"
            )

        return cls(
            stage=data["stage"],
            order=data["order"],
            error=data["error"],
            retry_count=data["retry_count"],
            recovered=data["recovered"],
            aborted=data["aborted"],
        )


@dataclass
class RecoveryPolicy:
    max_retries: int = 2
    allow_recovery: bool = True


@dataclass
class RecoveryState:
    failures: List[FailureRecord] = field(default_factory=list)
    current_stage: Optional[str] = None
    current_order: Optional[int] = None
    retry_count: int = 0
    recovered: bool = False
    aborted: bool = False

    def record_failure(
        self,
        stage: str,
        order: int,
        error: str,
    ) -> FailureRecord:
        if self.aborted:
            raise RuntimeError(
                "cannot record failure on aborted recovery state"
            )

        if self.recovered:
            raise RuntimeError(
                "cannot record failure on recovered recovery state"
            )

        if not isinstance(stage, str):
            raise TypeError("stage must be a string")

        if not stage.strip():
            raise ValueError("stage must not be empty")

        if not isinstance(order, int) or isinstance(order, bool):
            raise TypeError("order must be an integer")

        if order < 1 or order > 12:
            raise ValueError(
                "order must be between 1 and 12"
            )

        if not isinstance(error, str):
            raise TypeError("error must be a string")

        if not error.strip():
            raise ValueError("error must not be empty")

        expected_stages = (
            "conversation",
            "goal",
            "objective",
            "context",
            "constraints",
            "reasoning",
            "decision",
            "planner",
            "prediction",
            "verification",
            "reflection",
            "learning",
        )

        expected_stage = expected_stages[order - 1]

        if stage != expected_stage:
            raise ValueError(
                f"stage/order mismatch: "
                f"order {order} expects "
                f"{expected_stage}, got {stage}"
            )

        record = FailureRecord(
            stage=stage,
            order=order,
            error=error,
            retry_count=self.retry_count,
        )

        self.failures.append(record)
        self.current_stage = stage
        self.current_order = order

        return record

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failures": [
                failure.to_dict()
                for failure in self.failures
            ],
            "current_stage": self.current_stage,
            "current_order": self.current_order,
            "retry_count": self.retry_count,
            "recovered": self.recovered,
            "aborted": self.aborted,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(
        cls,
        value: str,
    ) -> "RecoveryState":
        if not isinstance(value, str):
            raise TypeError(
                "serialized recovery state must be a string"
            )

        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "invalid recovery state JSON"
            ) from exc

        return cls.from_dict(data)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "RecoveryState":
        if not isinstance(data, dict):
            raise TypeError(
                "recovery state must be a dictionary"
            )

        required = {
            "failures",
            "current_stage",
            "current_order",
            "retry_count",
            "recovered",
            "aborted",
        }

        if set(data.keys()) != required:
            raise ValueError(
                "invalid recovery state fields"
            )

        if not isinstance(data["failures"], list):
            raise TypeError(
                "failures must be a list"
            )

        failures = [
            FailureRecord.from_dict(item)
            for item in data["failures"]
        ]

        current_stage = data["current_stage"]
        current_order = data["current_order"]

        if current_stage is not None and not isinstance(
            current_stage,
            str,
        ):
            raise TypeError(
                "current_stage must be a string or None"
            )

        if current_order is not None:
            if not isinstance(current_order, int) or isinstance(
                current_order,
                bool,
            ):
                raise TypeError(
                    "current_order must be an integer or None"
                )

            if current_order < 1 or current_order > 12:
                raise ValueError(
                    "current_order must be between 1 and 12"
                )

        if not isinstance(data["retry_count"], int) or isinstance(
            data["retry_count"],
            bool,
        ):
            raise TypeError(
                "retry_count must be an integer"
            )

        if data["retry_count"] < 0:
            raise ValueError(
                "retry_count must not be negative"
            )

        if not isinstance(data["recovered"], bool):
            raise TypeError(
                "recovered must be boolean"
            )

        if not isinstance(data["aborted"], bool):
            raise TypeError(
                "aborted must be boolean"
            )

        if (
            current_stage is None
            and current_order is not None
        ):
            raise ValueError(
                "current_stage required when current_order exists"
            )

        if (
            current_stage is not None
            and current_order is None
        ):
            raise ValueError(
                "current_order required when current_stage exists"
            )

        if (
            current_order is not None
            and failures
        ):
            latest = failures[-1]

            if latest.order != current_order:
                raise ValueError(
                    "current_order does not match latest failure"
                )

            if latest.stage != current_stage:
                raise ValueError(
                    "current_stage does not match latest failure"
                )

        if data["recovered"] and data["aborted"]:
            raise ValueError(
                "recovery state cannot be both recovered and aborted"
            )

        state = cls(
            failures=failures,
            current_stage=current_stage,
            current_order=current_order,
            retry_count=data["retry_count"],
            recovered=data["recovered"],
            aborted=data["aborted"],
        )

        return state
