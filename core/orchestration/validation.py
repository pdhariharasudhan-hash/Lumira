#core/orchestration/validation.py
import re
from typing import Any, Dict, List, Optional, Tuple

from core.utils.helpers import (
    clean_string_list,
    is_non_empty_string,
    normalize_step
)

from core.generation.quality import (
    analyze_code_quality
)

REQUIRED_BUILDER_KEYS = {
    "objective",
    "scope",
    "suggested_steps",
    "status"
}

REQUIRED_EXECUTE_KEYS = {
    "execution_order",
    "today_task",
    "task_steps",
    "expected_output",
    "blockers",
    "status"
}

REQUIRED_CODE_KEYS = {
    "idea",
    "code_target",
    "file_plan",
    "implementation_steps",
    "test_steps",
    "priority",
    "status"
}

REQUIRED_VALIDATE_KEYS = {
    "idea",
    "weaknesses",
    "risks",
    "verdict",
    "risk_level"
}


VALID_VERBS = {
    "create",
    "build",
    "generate",
    "validate",
    "parse",
    "send",
    "fetch",
    "store",
    "update",
    "delete",
    "convert",
    "extract",
    "transform",
    "execute"
}

WEAK_VERBS = {
    "do",
    "make",
    "handle",
    "process",
    "start",
    "run"
}

GENERIC_PHRASES = {
    "do setup",
    "start building",
    "initialize system",
    "process data"
}


def is_valid_action(
    action: str
) -> bool:

    action = action.lower().strip()

    if len(action.split()) < 2:
        return False

    if action in GENERIC_PHRASES:
        return False

    words = action.split()

    if words[0] in WEAK_VERBS:
        return False

    if not any(
        word in VALID_VERBS
        for word in words
    ):
        return False

    return True


def is_step_aligned(
    action: str,
    keywords: List[str]
) -> bool:

    action_words = set(
        action.lower().split()
    )

    return any(
        keyword in action_words
        for keyword in keywords
    )


def score_step(
    action: str,
    keywords: List[str]
) -> int:

    score = 0

    if len(action.split()) >= 3:
        score += 2
    else:
        score += 1

    if is_valid_action(action):
        score += 2

    if is_step_aligned(
        action,
        keywords
    ):
        score += 2

    return score


def validate_step_structure(
    step: Dict[str, Any],
    valid_ids: set
) -> bool:

    if not isinstance(step, dict):
        return False

    required_keys = {
        "id",
        "action",
        "inputs",
        "expected_output",
        "dependencies"
    }

    if not required_keys.issubset(
        step.keys()
    ):
        return False

    if not is_non_empty_string(
        step["id"]
    ):
        return False

    if not is_non_empty_string(
        step["action"]
    ):
        return False

    if not isinstance(
        step["inputs"],
        dict
    ):
        return False

    if not is_non_empty_string(
        step["expected_output"]
    ):
        return False

    if not isinstance(
        step["dependencies"],
        list
    ):
        return False

    for dep in step["dependencies"]:

        if dep not in valid_ids:
            return False

    return True


def validate_builder_output(
    builder_output: Any
) -> Optional[str]:

    if not isinstance(
        builder_output,
        dict
    ):
        return "invalid_builder_output:not_dict"

    missing = (
        REQUIRED_BUILDER_KEYS
        - set(builder_output.keys())
    )

    if missing:

        return (
            f"invalid_builder_output:"
            f"missing_keys:{sorted(missing)}"
        )

    if not is_non_empty_string(
        builder_output.get(
            "objective"
        )
    ):
        return (
            "invalid_builder_output:"
            "bad_objective"
        )

    if not is_non_empty_string(
        builder_output.get(
            "scope"
        )
    ):
        return (
            "invalid_builder_output:"
            "bad_scope"
        )

    if builder_output.get(
        "status"
    ) not in {
        "accept",
        "fallback"
    }:
        return (
            "invalid_builder_output:"
            "status_not_accept"
        )

    steps = builder_output.get(
        "suggested_steps"
    )

    if (
        not isinstance(
            steps,
            list
        )
        or not steps
    ):
        return (
            "invalid_builder_output:"
            "bad_suggested_steps"
        )

    step_ids = set()

    for step in steps:

        if (
            not isinstance(
                step,
                dict
            )
            or "id" not in step
        ):
            return (
                "invalid_builder_output:"
                "invalid_step_format"
            )

        step_ids.add(
            step["id"]
        )

    for step in steps:

        if not validate_step_structure(
            step,
            step_ids
        ):
            return (
                "invalid_builder_output:"
                "invalid_step_structure"
            )

    return None


def looks_like_multi_step_today_task(
    today_task: str,
    builder_steps: List[str]
) -> bool:

    normalized_today = normalize_step(
        today_task
    )

    if normalized_today in {
        normalize_step(step)
        for step in builder_steps
    }:
        return False

    patterns = [
        r"\band then\b",
        r"\bthen\b",
        r"\bafter that\b",
        r"\bnext\b",
        r",\s*[a-z]",
        r";\s*[a-z]"
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            normalized_today
        ):
            return True

    return False


def validate_execute_output(
    execute_output: Any,
    builder_output: Dict[str, Any]
) -> Tuple[
    Optional[str],
    Optional[Dict[str, Any]]
]:

    if not isinstance(
        execute_output,
        dict
    ):
        return (
            "invalid_execute_output:not_dict",
            None
        )

    missing = (
        REQUIRED_EXECUTE_KEYS
        - set(execute_output.keys())
    )

    if missing:

        return (
            f"invalid_execute_output:"
            f"missing_keys:{sorted(missing)}",
            None
        )

    execution_order = execute_output.get(
        "execution_order"
    )

    if (
        not isinstance(
            execution_order,
            list
        )
        or not execution_order
    ):
        return (
            "invalid_execute_output:"
            "bad_execution_order",
            None
        )

    builder_steps = [
        step["id"]
        for step in builder_output.get(
            "suggested_steps",
            []
        )
        if isinstance(step, dict)
    ]

    if execution_order != builder_steps:

        return (
            "invalid_execute_output:"
            "execution_order_not_aligned",
            None
        )

    normalized = {
        "execution_order": execution_order,
        "today_task":
        execute_output[
            "today_task"
        ].strip(),

        "task_steps":
        clean_string_list(
            execute_output[
                "task_steps"
            ]
        ),

        "expected_output":
        execute_output[
            "expected_output"
        ].strip(),

        "blockers":
        execute_output[
            "blockers"
        ],

        "status":
        execute_output[
            "status"
        ]
    }

    return (
        None,
        normalized
    )


def validate_validate_stage_output(
    validate_output: Any
) -> bool:

    if not isinstance(
        validate_output,
        dict
    ):
        return False

    if not REQUIRED_VALIDATE_KEYS.issubset(
        validate_output.keys()
    ):
        return False

    return True


def validate_builder_stage_output(
    builder_output: Any
) -> bool:

    if (
        validate_builder_output(
            builder_output
        )
        is not None
    ):
        return False

    return True


def validate_execute_stage_output_for_memory(
    execute_output: Any,
    builder_output: Any
) -> bool:

    error, normalized = (
        validate_execute_output(
            execute_output,
            builder_output
        )
    )

    return (
        error is None
        and normalized is not None
    )


def validate_code_stage_output(
    code_output: Any
) -> bool:

    if not isinstance(
        code_output,
        dict
    ):
        return False

    if not REQUIRED_CODE_KEYS.issubset(
        code_output.keys()
    ):
        return False

    quality = analyze_code_quality(
        code_output
    )

    return quality["passed"]