from typing import Any, Dict

import requests

from core.constants import BASE_URL
from core.infrastructure.fallback import (
    build_fallback_response
)


def post_json_request(
    endpoint: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:

    try:

        response = requests.post(
            f"{BASE_URL}/{endpoint}",
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException:

        return build_fallback_response(
            endpoint,
            payload
        )


def post_request(
    endpoint: str,
    text: str
) -> Dict[str, Any]:

    return post_json_request(
        endpoint,
        {"input": text}
    )