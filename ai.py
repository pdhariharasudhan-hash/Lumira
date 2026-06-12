import json
import re
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, UTC
from core.generation.artifact_generator import materialize_code_output
from core.constants import (
    BASE_URL,
    GENERATED_DIR,
    MAX_RETRIES,
    PIPELINE_MEMORY_BACKUP_FILE,
    PIPELINE_MEMORY_FILE
)

from core.infrastructure.health import (
    check_backend_health
)

from core.infrastructure.requests import (
    post_json_request,
    post_request
)

from core.utils.helpers import (
    add_unique,
    clean_string_list,
    extract_keywords,
    is_non_empty_string,
    normalize_step,
    normalize_text,
    now
)

from core.memory.storage import (
    append_pipeline_run,
    get_latest_pipeline,
    load_fallback_pipeline,
    post_memory_get,
    save_adaptive_rules,
    save_learning_insights,
    save_pipeline
)
from core.orchestration.validation import (
    validate_builder_output,
    validate_execute_output,
    validate_validate_stage_output,
    validate_builder_stage_output,
    validate_execute_stage_output_for_memory,
    validate_code_stage_output
)

from core.orchestration.pipeline import (
    VALID_STAGES,
    next_stage,
    clear_downstream,
    add_pipeline_trace,
    add_state_fix,
    append_improvement_once
)

from core.orchestration.executor import (
    run_stage,
    execute_pipeline
)

MAX_COMPLETED_RUNS_PER_INPUT = 2
MAX_FAILED_RUNS_PER_INPUT = 1
MAX_REJECTED_RUNS_PER_INPUT = 1
MAX_REFINE_RUNS_PER_INPUT = 1
MAX_INCOMPLETE_RUNS_PER_INPUT = 1



# -------------------------
# BUILDER QUALITY HELPERS
# -------------------------
STOPWORDS = {
    "the","is","at","which","on","a","an","and","or","to",
    "for","of","in","with","by","from","as","it"
}


def extract_stage_result(response: Dict[str, Any]) -> Dict[str, Any]:
    data = response.get("data", {})
    return data.get("result") if isinstance(data.get("result"), dict) else data



    

def build_pipeline_payload(text: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": "pipeline_run",
        "input": text,
        "validate": None,
        "builder": None,
        "execute": None,
        "code": None,
        "current_stage": "validate",
        "last_completed_stage": None,
        "status": "running",
        "final_status": "incomplete",
        "error": None,
        "retry_count": 0,
        "resume_allowed": True,
        "aborted": False,
        "manual_override": None,
        "state_fixes": [],
        "pipeline_trace": []
    }


def synthesize_execute_refine(
    payload: Dict[str, Any],
    builder_output: Dict[str, Any],
    reason: str
) -> Dict[str, Any]:

    steps_raw = builder_output.get("suggested_steps", [])

    if not isinstance(steps_raw, list):
        steps_raw = []

    step_ids = [
        step["id"]
        for step in steps_raw
        if isinstance(step, dict) and "id" in step
    ]

    if not step_ids:
        return {
            "execution_order": [],
            "today_task": "refine_builder_output",
            "task_steps": [f"Fix builder issue: {reason}"],
            "expected_output": "builder output fixed",
            "blockers": [reason],
            "status": "refine"
        }

    return {
        "execution_order": step_ids,
        "today_task": step_ids[0],
        "task_steps": [f"Fix builder alignment issue: {reason}"],
        "expected_output": "Aligned execute plan",
        "blockers": [reason],
        "status": "refine"
    }
        
def run_pipeline(
    text: str
) -> None:

    payload = build_pipeline_payload(
        text
    )

    memory = post_memory_get()

    adaptive_rules = {}

    if memory:

        adaptive_rules = memory.get(
            "adaptive_rules",
            {}
        )

    payload[
        "adaptive_rules"
    ] = adaptive_rules

    save_pipeline(
        payload
    )

    print(
        json.dumps(
            execute_pipeline(
                payload
            ),
            indent=2
        )
    )

def continue_pipeline() -> None:
    payload = get_latest_pipeline()

    if not payload:
        print("No pipeline")
        return

    if payload.get("aborted") is True:
        print("Blocked: pipeline aborted")
        return

    if payload.get("status") == "completed" or payload.get("final_status") == "completed":
        print("Blocked: already completed")
        return

    if payload.get("final_status") == "rejected":
        print("Blocked: rejected runs cannot continue")
        return

    if payload.get("resume_allowed") is False:
        print("Blocked: resume not allowed")
        return

    current_stage = payload.get("current_stage")
    if current_stage not in VALID_STAGES:
        print("Blocked: invalid current stage")
        return

    print(json.dumps(execute_pipeline(payload), indent=2))


def reset_pipeline() -> None:
    payload = get_latest_pipeline()

    if not payload:
        print("No pipeline")
        return

    final_status = payload.get("final_status")
    current_stage = payload.get("current_stage")

    if payload.get("status") == "completed" or final_status == "completed":
        print("Blocked: completed pipeline cannot reset")
        return

    if final_status == "rejected":
        print("Blocked: rejected pipeline cannot reset")
        return

    if current_stage not in VALID_STAGES:
        print("Blocked: invalid current stage")
        return

    stage_before = current_stage

    payload["status"] = "stopped"
    payload["error"] = None
    payload["retry_count"] = 0
    payload["resume_allowed"] = True
    payload["aborted"] = False
    payload["final_status"] = "incomplete"

    add_state_fix(
        payload,
        category="reset",
        issue="manual reset requested",
        fix="cleared error and retry state",
        stage_before=stage_before,
        stage_after=current_stage
    )

    save_pipeline(payload)
    print(json.dumps(payload, indent=2))


def abort_pipeline() -> None:
    payload = get_latest_pipeline()

    if not payload:
        print("No pipeline")
        return

    if payload.get("status") == "completed" or payload.get("final_status") == "completed":
        print("Blocked: completed pipeline cannot abort")
        return

    stage_before = payload.get("current_stage")

    payload["status"] = "stopped"
    payload["aborted"] = True
    payload["resume_allowed"] = False
    payload["error"] = None

    add_state_fix(
        payload,
        category="abort",
        issue="manual abort requested",
        fix="pipeline permanently stopped until reset or new run",
        stage_before=stage_before,
        stage_after=stage_before
    )

    save_pipeline(payload)
    print(json.dumps(payload, indent=2))


def show_memory() -> None:
    memory = post_memory_get()
    fallback = load_fallback_pipeline()

    result = {
        "backend_memory_available": memory is not None,
        "fallback_pipeline_available": fallback is not None,
        "backend_memory": memory,
        "fallback_pipeline": fallback
    }

    print(json.dumps(result, indent=2))




def build_adaptive_rules(
    failure_patterns: List[Dict[str, Any]],
    recommended_upgrades: List[str]
) -> Dict[str, Any]:
    rules: Dict[str, Any] = {
        "validate": {
            "reject_exact_inputs": [],
            "reject_patterns": [],
            "strict_short_input": False
        },
        "builder": {
            "force_step_repair": False
        },
        "execute": {
            "force_builder_alignment": True
        },
        "code": {
            "force_specific_file_plan": False,
            "force_specific_test_steps": False
        },
        "generated_at": now(),
        "source": "learning_engine"
    }

    for pattern in failure_patterns:
        stage = pattern.get("stage")
        examples = pattern.get("examples", [])

        if stage == "validate":
            for example in examples:
                cleaned = normalize_text(str(example))

                if not cleaned:
                    continue

                word_count = len(cleaned.split())

                if word_count <= 2:
                    add_unique(rules["validate"]["reject_exact_inputs"], cleaned)

                if cleaned in {"build app", "make ai", "test"}:
                    add_unique(
                        rules["validate"]["reject_patterns"],
                        f"^{re.escape(cleaned)}$"
                    )

            rules["validate"]["strict_short_input"] = True

        elif stage == "builder":
            rules["builder"]["force_step_repair"] = True

        elif stage == "execute":
            rules["execute"]["force_builder_alignment"] = True

        elif stage == "code":
            rules["code"]["force_specific_file_plan"] = True
            rules["code"]["force_specific_test_steps"] = True

    for rec in recommended_upgrades:
        lowered = rec.lower()

        if "validation rules" in lowered:
            rules["validate"]["strict_short_input"] = True

        if "builder step generation" in lowered:
            rules["builder"]["force_step_repair"] = True

        if "execute-builder alignment" in lowered:
            rules["execute"]["force_builder_alignment"] = True

        if "file_plan" in lowered or "test_steps" in lowered:
            rules["code"]["force_specific_file_plan"] = True
            rules["code"]["force_specific_test_steps"] = True

    rules["validate"]["reject_exact_inputs"] = sorted(
        list(set(rules["validate"]["reject_exact_inputs"]))
    )
    rules["validate"]["reject_patterns"] = sorted(
        list(set(rules["validate"]["reject_patterns"]))
    )

    return rules


def learn_from_memory() -> None:

    memory = post_memory_get()

    if not memory:

        print(
            "Learning unavailable: backend memory not reachable"
        )

        return

    runs = memory.get(
        "pipeline_runs",
        []
    )

    total = len(runs)

    completed = 0
    failed = 0
    rejected = 0
    refined = 0

    stage_failures: Dict[str, int] = {}

    failure_patterns: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for run in runs:

        final_status = run.get(
            "final_status"
        )

        user_input = run.get(
            "input",
            ""
        ).lower()

        if final_status == "completed":

            completed += 1
            continue

        if final_status == "failed":

            failed += 1

        elif final_status == "rejected":

            rejected += 1

        elif final_status == "refine_required":

            refined += 1

        failed_stage = run.get(
            "current_stage"
        )

        error_reason = str(
            run.get(
                "error",
                ""
            )
        ).lower()

        if failed_stage:

            stage_failures[
                failed_stage
            ] = (
                stage_failures.get(
                    failed_stage,
                    0
                ) + 1
            )

            keywords = extract_keywords(
                user_input
            )

            error_keywords = extract_keywords(
                error_reason
            )

            for k in error_keywords:

                if k not in keywords:

                    keywords.append(
                        k
                    )

            security_words = {
                "password",
                "username",
                "token",
                "secret",
                "auth"
            }

            important = []

            for word in keywords:

                if word in security_words:

                    important.append(
                        word
                    )

            if "auth" in keywords:

                core_keywords = [
                    "auth"
                ]

            else:

                core_keywords = important[:1]

            if "invalid" in keywords:

                core_keywords.append(
                    "invalid"
                )

            core_keywords = sorted(
                list(
                    set(
                        core_keywords
                    )
                )
            )

            key = (
                f"{failed_stage}:"
                f"{'-'.join(core_keywords)}"
            )

            if key not in failure_patterns:

                failure_patterns[
                    key
                ] = {
                    "stage": failed_stage,
                    "count": 0,
                    "examples": [],
                    "keywords": keywords[:5]
                }

            failure_patterns[
                key
            ]["count"] += 1

            if len(
                failure_patterns[
                    key
                ]["examples"]
            ) < 3:

                failure_patterns[
                    key
                ][
                    "examples"
                ].append(
                    run.get(
                        "input"
                    )
                )

    most_failed_stage = None

    if stage_failures:

        highest = max(
            stage_failures.values()
        )

        most_failed_stage = [

            stage

            for stage, count
            in stage_failures.items()

            if count == highest
        ]

    recommendations: List[
        str
    ] = []

    for pattern in failure_patterns.values():

        stage = pattern[
            "stage"
        ]

        keywords = pattern[
            "keywords"
        ]

        if stage == "execute":

            recommendations.append(
                f"Strengthen execute-builder alignment for keywords: {keywords}"
            )

        elif stage == "code":

            recommendations.append(
                f"Improve file_plan/test_steps generation for keywords: {keywords}"
            )

        elif stage == "builder":

            recommendations.append(
                f"Improve builder step generation for keywords: {keywords}"
            )

        elif stage == "validate":

            recommendations.append(
                f"Refine validation rules for keywords: {keywords}"
            )

    recommendation_list = sorted(
        list(
            set(
                recommendations
            )
        )
    )

    failure_pattern_list = list(
        failure_patterns.values()
    )

    adaptive_rules = build_adaptive_rules(
        failure_pattern_list,
        recommendation_list
    )

    result = {

        "total_runs": total,

        "completed_runs": completed,

        "failed_runs": failed,

        "rejected_runs": rejected,

        "refine_required_runs": refined,

        "most_failed_stage": most_failed_stage,

        "stage_failure_distribution": stage_failures,

        "failure_patterns": failure_pattern_list,

        "recommended_upgrades": recommendation_list,

        "adaptive_rules": adaptive_rules,

        "timestamp": now()
    }

    save_learning_insights(
        result
    )

    save_adaptive_rules(
        adaptive_rules
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )

def is_valid_pipeline_run(run: Any) -> bool:
    if not isinstance(run, dict):
        return False

    required_top_keys = {
        "id",
        "type",
        "input",
        "validate",
        "builder",
        "execute",
        "code",
        "current_stage",
        "last_completed_stage",
        "status",
        "final_status",
        "error",
        "retry_count",
        "resume_allowed",
        "aborted",
        "manual_override",
        "state_fixes",
    }

    if not required_top_keys.issubset(run.keys()):
        return False

    if run.get("type") != "pipeline_run":
        return False

    run_id = run.get("id")
    if not isinstance(run_id, str) or not run_id.strip():
        return False

    input_text = run.get("input")
    if not isinstance(input_text, str) or not input_text.strip():
        return False

    current_stage = run.get("current_stage")
    last_completed_stage = run.get("last_completed_stage")
    status = run.get("status")
    final_status = run.get("final_status")

    if current_stage not in VALID_STAGES.union({None}):
        return False

    if last_completed_stage not in VALID_STAGES.union({None}):
        return False

    if status not in {"running", "stopped", "completed", "retrying"}:
        return False

    if final_status not in {"incomplete","completed","rejected","failed","refine_required","retrying"}:
        return False

    if not isinstance(run.get("retry_count"), int):
        return False

    if not isinstance(run.get("resume_allowed"), bool):
        return False

    if not isinstance(run.get("aborted"), bool):
        return False

    if run.get("state_fixes") is not None and not isinstance(run.get("state_fixes"), list):
        return False

    # Purge obsolete known-bug runs from memory
    if isinstance(run.get("error"), str):
        if "today_task_not_atomic" in run["error"]:
            return False

    execute_stage = run.get("execute")
    if isinstance(execute_stage, dict):
        blockers = execute_stage.get("blockers", [])
        if any("today_task_not_atomic" in str(b) for b in blockers):
            return False

    validate_stage = run.get("validate")
    builder_stage = run.get("builder")
    code_stage = run.get("code")

    if final_status in {"completed", "rejected", "failed", "refine_required"} and not validate_validate_stage_output(validate_stage):
        return False

    if builder_stage is not None and not validate_builder_stage_output(builder_stage):
        return False

    if execute_stage is not None:
        if builder_stage is None:
            return False
        if not validate_execute_stage_output_for_memory(execute_stage, builder_stage):
            return False

    if code_stage is not None and not validate_code_stage_output(code_stage):
        return False

    if final_status == "completed":
        if not all([validate_stage, builder_stage, execute_stage, code_stage]):
            return False
        if current_stage is not None:
            return False
        if last_completed_stage != "code":
            return False
        if status != "completed":
            return False
        if run.get("resume_allowed") is not False:
            return False

    if final_status == "rejected":
        if validate_stage is None:
            return False
        if validate_stage.get("verdict") != "reject":
            return False
        if any(stage is not None for stage in [builder_stage, execute_stage, code_stage]):
            return False

    if final_status == "refine_required":
        if execute_stage is None and builder_stage is None:
            return False

    return True


def pipeline_quality_score(run: Dict[str, Any]) -> Tuple[int, int, int, int]:
    status_rank = {
        "completed": 5,
        "refine_required": 4,
        "failed": 3,
        "rejected": 2,
        "incomplete": 1,
    }.get(run.get("final_status"), 0)

    completed_stage_count = sum(
        1 for key in ["validate", "builder", "execute", "code"]
        if isinstance(run.get(key), dict)
    )

    state_fix_count = len(run.get("state_fixes") or [])
    retry_score = -int(run.get("retry_count", 0))

    return (status_rank, completed_stage_count, state_fix_count, retry_score)


def choose_best_run(existing: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    existing_score = pipeline_quality_score(existing)
    candidate_score = pipeline_quality_score(candidate)
    return candidate if candidate_score > existing_score else existing




def sort_runs_best_first(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(runs, key=pipeline_quality_score, reverse=True)


def split_runs_by_status(runs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets = {
        "completed": [],
        "failed": [],
        "rejected": [],
        "refine_required": [],
        "incomplete": [],
    }
    for run in runs:
        buckets.setdefault(run.get("final_status", "incomplete"), []).append(run)
    return buckets


def select_runs_per_input(runs: List[Dict[str, Any]], keep_ids: Optional[set] = None) -> List[Dict[str, Any]]:
    keep_ids = keep_ids or set()
    buckets = split_runs_by_status(runs)

    selected: List[Dict[str, Any]] = []

    def pick(status: str, limit: int) -> None:
        chosen = sort_runs_best_first(buckets.get(status, []))
        forced = [r for r in chosen if r.get("id") in keep_ids]
        normal = [r for r in chosen if r.get("id") not in keep_ids]

        taken_ids = set()
        for run in forced:
            if run["id"] not in taken_ids:
                selected.append(run)
                taken_ids.add(run["id"])

        remaining_slots = max(0, limit - len(taken_ids))
        for run in normal[:remaining_slots]:
            if run["id"] not in taken_ids:
                selected.append(run)
                taken_ids.add(run["id"])

    pick("completed", MAX_COMPLETED_RUNS_PER_INPUT)
    pick("failed", MAX_FAILED_RUNS_PER_INPUT)
    pick("rejected", MAX_REJECTED_RUNS_PER_INPUT)
    pick("refine_required", MAX_REFINE_RUNS_PER_INPUT)
    pick("incomplete", MAX_INCOMPLETE_RUNS_PER_INPUT)

    return selected


def smart_cleanup_memory() -> None:
    memory = post_memory_get()

    if not memory:
        print("Cleanup unavailable: backend memory not reachable")
        return

    safe_write_json(CLEANUP_BACKUP_PATH, memory)

    original_runs = memory.get("pipeline_runs", [])
    latest_pipeline = memory.get("latest_pipeline_run")

    invalid_count = 0
    duplicate_id_count = 0

    deduped_by_id: Dict[str, Dict[str, Any]] = {}
    for run in original_runs:
        if not is_valid_pipeline_run(run):
            invalid_count += 1
            continue

        run_id = run["id"]
        if run_id in deduped_by_id:
            duplicate_id_count += 1
            deduped_by_id[run_id] = choose_best_run(deduped_by_id[run_id], run)
        else:
            deduped_by_id[run_id] = run

    keep_ids = set()
    if is_valid_pipeline_run(latest_pipeline):
        latest_id = latest_pipeline["id"]
        keep_ids.add(latest_id)
        if latest_id in deduped_by_id:
            deduped_by_id[latest_id] = choose_best_run(deduped_by_id[latest_id], latest_pipeline)
        else:
            deduped_by_id[latest_id] = latest_pipeline
    else:
        latest_pipeline = None

    deduped_runs = list(deduped_by_id.values())

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for run in deduped_runs:
        key = normalized_input_key(run["input"])
        grouped.setdefault(key, []).append(run)

    cleaned_runs: List[Dict[str, Any]] = []
    removed_same_input_noise = 0

    for _, runs_for_input in grouped.items():
        before_count = len(runs_for_input)
        kept = select_runs_per_input(runs_for_input, keep_ids=keep_ids)
        cleaned_runs.extend(kept)
        removed_same_input_noise += max(0, before_count - len(kept))

    if latest_pipeline and latest_pipeline["id"] not in {r["id"] for r in cleaned_runs}:
        cleaned_runs.append(latest_pipeline)

    if not latest_pipeline and cleaned_runs:
        latest_pipeline = max(cleaned_runs, key=pipeline_quality_score)

    res_all = post_memory_update("pipeline_runs", cleaned_runs)
    res_latest = post_memory_update("latest_pipeline_run", latest_pipeline)

    if res_all.get("status") != "ok" or res_latest.get("status") != "ok":
        print("Cleanup failed: could not write cleaned memory back to backend")
        return

    result = {
        "cleanup": "smart_complete",
        "original_runs": len(original_runs),
        "cleaned_runs": len(cleaned_runs),
        "removed_invalid_runs": invalid_count,
        "removed_duplicate_id_entries": duplicate_id_count,
        "removed_same_input_noise": removed_same_input_noise,
        "backup_path": CLEANUP_BACKUP_PATH,
        "latest_pipeline_run_id": latest_pipeline.get("id") if isinstance(latest_pipeline, dict) else None
    }

    print(json.dumps(result, indent=2))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python ai.py <run|continue|reset|abort|cleanup|learn|memory>")
        return

    cmd = sys.argv[1].strip().lower()

    if cmd == "run":
        text = " ".join(sys.argv[2:]).strip()
        if not text:
            print('Usage: python ai.py run "<text>"')
            return
        run_pipeline(text)

    elif cmd == "continue":
        continue_pipeline()

    elif cmd == "reset":
        reset_pipeline()

    elif cmd == "abort":
        abort_pipeline()

    elif cmd == "cleanup":
        smart_cleanup_memory()

    elif cmd == "learn":
        learn_from_memory()

    elif cmd == "memory":
        show_memory()

    else:
        print("Invalid command")


if __name__ == "__main__":
    main()