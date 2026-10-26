#core/orchestration/pipeline.py
from typing import Any, Dict

from core.constants import MAX_RETRIES
from core.generation.artifact_generator import (
    materialize_code_output
)

from core.infrastructure.health import (
    check_backend_health
)

from core.infrastructure.requests import (
    post_json_request
)

from core.memory.storage import (
    append_pipeline_run,
    save_pipeline
)

from core.orchestration.pipeline import (
    add_pipeline_trace,
    add_state_fix,
    append_improvement_once,
    clear_downstream,
    next_stage
)

from core.orchestration.validation import (
    validate_builder_output,
    validate_execute_output
)

from core.orchestration.validation import (
    validate_builder_output,
    validate_execute_output,
    validate_code_stage_output
)

from core.generation.quality import (
    analyze_code_quality
)

def run_stage(
    payload: Dict[str, Any],
    stage: str
) -> bool:

    print(
        f"RUNNING {stage.upper()}"
    )

    add_pipeline_trace(
        payload,
        stage=stage,
        event="stage_started"
    )

    health = (
        check_backend_health()
    )

    if not health.get(
        stage,
        False
    ):

        payload.setdefault(
            "degraded_stages",
            []
        )

        if stage not in payload[
            "degraded_stages"
        ]:

            payload[
                "degraded_stages"
            ].append(
                stage
            )

        payload[
            "status"
        ] = "stopped"

        payload[
            "final_status"
        ] = "refine_required"

        payload[
            "current_stage"
        ] = stage

        payload[
            "resume_allowed"
        ] = True

        payload[
            "error"
        ] = (
            f"{stage} "
            "backend unavailable"
        )

        add_state_fix(
            payload,
            category="health_check",
            issue="service unavailable",
            fix="stage blocked before execution",
            stage_before=stage,
            stage_after=stage
        )

        add_pipeline_trace(
            payload,
            stage=stage,
            event="health_check_failed",
            details={
                "reason":
                "backend unavailable"
            }
        )

        save_pipeline(
            payload
        )

        return False

    if stage == "execute":

        builder_output = payload.get(
            "builder"
        )

        builder_error = (
            validate_builder_output(
                builder_output
            )
        )

        if builder_error:

            payload[
                "status"
            ] = "stopped"

            payload[
                "error"
            ] = builder_error

            payload[
                "final_status"
            ] = (
                "refine_required"
            )

            payload[
                "resume_allowed"
            ] = True

            save_pipeline(
                payload
            )

            return False

        res = post_json_request(
            "execute",
            {
                "input":
                payload["input"],

                "builder":
                builder_output,

                "improvements":
                payload.get(
                    "improvements",
                    []
                )
            }
        )

    elif stage == "code":

        res = post_json_request(
            "code",
            {
                "input":
                payload["input"],

                "execute":
                payload[
                    "execute"
                ],

                "improvements":
                payload.get(
                    "improvements",
                    []
                )
            }
        )

    else:

        res = post_json_request(
            stage,
            {
                "input":
                payload["input"],

                "improvements":
                payload.get(
                    "improvements",
                    []
                )
            }
        )

    if res.get(
        "status"
    ) not in {
        "ok",
        "degraded"
    }:

        payload[
            "status"
        ] = "stopped"

        payload[
            "error"
        ] = res.get(
            "error"
        )

        payload[
            "retry_count"
        ] += 1

        save_pipeline(
            payload
        )

        return False

    result = (
        res.get(
            "data",
            {}
        ).get(
            "result",
            {}
        )
    )
    
    if stage == "code":

        quality = analyze_code_quality(
            result
        )

        if not quality["passed"]:

            payload["status"] = "stopped"

            payload["error"] = (
                "invalid_code_output:"
                + ",".join(
                    quality["issues"]
                )
            )

            payload["final_status"] = (
                "refine_required"
            )

            payload["resume_allowed"] = True

            add_state_fix(
                payload,
                category="code_quality",
                issue="generated code rejected",
                fix="quality validation failed",
                stage_before="code",
                stage_after="code"
            )

            save_pipeline(
                payload
            )

            return False

    if stage == "execute":

        error, normalized = (
            validate_execute_output(
                result,
                payload[
                    "builder"
                ]
            )
        )

        if error:

            payload[
                "status"
            ] = "stopped"

            payload[
                "error"
            ] = error

            payload[
                "resume_allowed"
            ] = True

            save_pipeline(
                payload
            )

            return False

        result = normalized

    payload[
        stage
    ] = result

    payload[
        "last_completed_stage"
    ] = stage

    add_pipeline_trace(
        payload,
        stage=stage,
        event="stage_completed"
    )

    payload[
        "current_stage"
    ] = next_stage(
        stage
    )

    save_pipeline(
        payload
    )

    return True


def execute_pipeline(
    payload: Dict[str, Any]
) -> Dict[str, Any]:

    while True:

        if "improvements" not in payload:

            payload["improvements"] = []

        adaptive = payload.get(
            "adaptive_rules",
            {}
        )

        code_rules = adaptive.get(
            "code",
            {}
        )

        if code_rules.get(
            "force_specific_file_plan"
        ):

            append_improvement_once(
                payload,
                {
                    "type": "adaptive_file_plan",
                    "reason": "learning requires stronger file planning",
                    "severity": "high"
                }
            )

        if code_rules.get(
            "force_specific_test_steps"
        ):

            append_improvement_once(
                payload,
                {
                    "type": "adaptive_tests",
                    "reason": "learning requires stronger test generation",
                    "severity": "high"
                }
            )

        while payload.get(
            "current_stage"
        ) is not None:

            if not run_stage(
                payload,
                payload["current_stage"]
            ):

                append_pipeline_run(
                    payload
                )

                return payload

        pipeline_valid = (

            payload.get(
                "validate"
            )

            and payload.get(
                "builder"
            )

            and payload.get(
                "execute"
            )

            and payload.get(
                "code"
            )

            and payload[
                "builder"
            ].get(
                "status"
            ) == "accept"

            and payload[
                "execute"
            ].get(
                "status"
            ) == "accept"

            and payload[
                "code"
            ].get(
                "status"
            ) == "accept"

            and not payload.get(
                "degraded_stages"
            )
        )

        if pipeline_valid:

            payload[
                "status"
            ] = "completed"

            payload[
                "final_status"
            ] = "completed"

            payload[
                "resume_allowed"
            ] = False

            payload[
                "error"
            ] = None

            payload[
                "retry_count"
            ] = 0

            artifact_result = (
                materialize_code_output(
                    payload["code"],
                    payload["id"]
                )
            )

            payload[
                "artifacts"
            ] = artifact_result

            add_pipeline_trace(
                payload,
                stage="pipeline",
                event="pipeline_completed",
                details={
                    "final_status":
                    "completed"
                }
            )

            save_pipeline(
                payload
            )

            append_pipeline_run(
                payload
            )

            return payload

        if payload[
            "retry_count"
        ] >= MAX_RETRIES:

            payload[
                "status"
            ] = "stopped"

            payload[
                "final_status"
            ] = "refine_required"

            payload[
                "current_stage"
            ] = "code"

            payload[
                "resume_allowed"
            ] = True

            save_pipeline(
                payload
            )

            append_pipeline_run(
                payload
            )

            return payload

        payload[
            "retry_count"
        ] += 1

        add_state_fix(
            payload,
            category="auto_retry",
            issue="pipeline output not acceptable",
            fix="retrying pipeline with structured improvements",
            stage_before="code",
            stage_after="validate"
        )

        payload[
            "validate"
        ] = None

        payload[
            "builder"
        ] = None

        payload[
            "execute"
        ] = None

        payload[
            "code"
        ] = None

        payload[
            "current_stage"
        ] = "validate"

        payload[
            "status"
        ] = "retrying"

        payload[
            "final_status"
        ] = "retrying"

        save_pipeline(
            payload
        )