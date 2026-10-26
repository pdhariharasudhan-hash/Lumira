#core/memory/storage.py
import json
import os
from typing import Any, Dict, Optional

import requests

from core.constants import (
    BASE_URL
)

from core.utils.helpers import (
    normalize_text
)


DATA_DIR = "data"

FALLBACK_PIPELINE_PATH = os.path.join(
    DATA_DIR,
    "cli_fallback_pipeline.json"
)


def ensure_data_dir() -> None:

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )


def safe_write_json(
    path: str,
    payload: Any
) -> None:

    ensure_data_dir()

    tmp_path = f"{path}.tmp"

    with open(
        tmp_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            payload,
            f,
            indent=2
        )

    os.replace(
        tmp_path,
        path
    )


def safe_read_json(
    path: str
) -> Optional[Dict[str, Any]]:

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return None

        return data

    except Exception:
        return None


def delete_file_if_exists(
    path: str
) -> None:

    try:

        if os.path.exists(path):

            os.remove(path)

    except Exception:
        pass


def post_memory_get() -> Optional[Dict[str, Any]]:

    try:

        response = requests.get(
            f"{BASE_URL}/memory/__full_memory__",
            timeout=30
        )

        if response.status_code == 404:
            return {}

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "ok":
            return None

        value = data.get(
            "data",
            {}
        ).get(
            "value",
            {}
        )

        if not isinstance(value, dict):
            return {}

        return value

    except Exception:
        return None


def post_memory_update(
    key: str,
    value: Any
) -> Dict[str, Any]:

    try:

        memory = post_memory_get()

        if memory is None:
            memory = {}

        memory[key] = value

        response = requests.post(
            f"{BASE_URL}/memory",
            json={
                "key": "__full_memory__",
                "value": memory
            },
            timeout=30
        )

        response.raise_for_status()

        return {
            "status": "ok",
            "data": response.json()
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }


def save_fallback_pipeline(
    payload: Dict[str, Any]
) -> None:

    safe_write_json(
        FALLBACK_PIPELINE_PATH,
        payload
    )


def load_fallback_pipeline() -> Optional[Dict[str, Any]]:

    return safe_read_json(
        FALLBACK_PIPELINE_PATH
    )


def save_pipeline(
    payload: Dict[str, Any]
) -> bool:

    result = post_memory_update(
        "latest_pipeline_run",
        payload
    )

    if result.get("status") == "ok":

        delete_file_if_exists(
            FALLBACK_PIPELINE_PATH
        )

        return True

    save_fallback_pipeline(
        payload
    )

    return False


def append_pipeline_run(
    payload: Dict[str, Any]
) -> bool:

    memory = post_memory_get()

    if memory is None:
        memory = {}

    runs = memory.get(
        "pipeline_runs",
        []
    )

    if not isinstance(runs, list):
        runs = []

    for run in runs:

        if not isinstance(run, dict):
            continue

        if run.get("id") == payload.get("id"):
            return True

    runs.append(payload)

    result = post_memory_update(
        "pipeline_runs",
        runs
    )

    return result.get("status") == "ok"


def save_learning_insights(
    insights: Dict[str, Any]
) -> bool:

    result = post_memory_update(
        "learning_insights",
        insights
    )

    return result.get("status") == "ok"


def save_adaptive_rules(
    rules: Dict[str, Any]
) -> bool:

    result = post_memory_update(
        "adaptive_rules",
        rules
    )

    return result.get("status") == "ok"


def sync_fallback_to_backend_if_possible() -> bool:

    fallback = load_fallback_pipeline()

    if not fallback:
        return False

    result = post_memory_update(
        "latest_pipeline_run",
        fallback
    )

    if result.get("status") != "ok":
        return False

    append_pipeline_run(
        fallback
    )

    delete_file_if_exists(
        FALLBACK_PIPELINE_PATH
    )

    return True


def get_latest_pipeline() -> Optional[Dict[str, Any]]:

    sync_fallback_to_backend_if_possible()

    memory = post_memory_get()

    backend_payload = None

    if isinstance(memory, dict):

        backend_payload = memory.get(
            "latest_pipeline_run"
        )

    if isinstance(
        backend_payload,
        dict
    ):
        return backend_payload

    fallback_payload = load_fallback_pipeline()

    if isinstance(
        fallback_payload,
        dict
    ):
        return fallback_payload

    return None


def normalized_input_key(
    text: str
) -> str:

    return normalize_text(
        text
    )