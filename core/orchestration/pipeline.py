#core/orchestration/pipeline.py
from typing import Any, Dict, Optional

from core.constants import MAX_RETRIES
from core.generation.artifact_generator import materialize_code_output
from core.infrastructure.health import check_backend_health
from core.infrastructure.requests import post_json_request

from core.memory.storage import (
    append_pipeline_run,
    save_pipeline
)

from core.orchestration.validation import (
    validate_builder_output,
    validate_execute_output
)

from core.utils.helpers import now


VALID_STAGES = {
    "validate",
    "builder",
    "execute",
    "code"
}


def next_stage(
    stage: Optional[str]
) -> Optional[str]:

    return {
        "validate": "builder",
        "builder": "execute",
        "execute": "code",
        "code": None
    }.get(stage)


def clear_downstream(
    payload: Dict[str, Any],
    stage: str
) -> None:

    order = [
        "validate",
        "builder",
        "execute",
        "code"
    ]

    idx = order.index(stage)

    for s in order[idx + 1:]:

        payload[s] = None


def add_pipeline_trace(
    payload: Dict[str, Any],
    stage: str,
    event: str,
    details: Optional[Dict[str, Any]] = None
) -> None:

    payload.setdefault(
        "pipeline_trace",
        []
    )

    payload["pipeline_trace"].append({
        "timestamp": now(),
        "stage": stage,
        "event": event,
        "details": details or {}
    })


def add_state_fix(
    payload: Dict[str, Any],
    category: str,
    issue: str,
    fix: str,
    stage_before=None,
    stage_after=None
) -> None:

    payload.setdefault(
        "state_fixes",
        []
    )

    payload["state_fixes"].append({
        "timestamp": now(),
        "category": category,
        "issue": issue,
        "fix": fix,
        "stage_before": stage_before,
        "stage_after": stage_after
    })


def append_improvement_once(
    payload: Dict[str, Any],
    improvement: Dict[str, Any]
) -> None:

    payload.setdefault(
        "improvements",
        []
    )

    existing = payload[
        "improvements"
    ]

    improvement_type = improvement.get(
        "type"
    )

    for item in existing:

        if not isinstance(
            item,
            dict
        ):
            continue

        if item.get(
            "type"
        ) == improvement_type:

            return

    existing.append(
        improvement
    )