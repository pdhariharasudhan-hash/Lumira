from typing import Any, Dict

import requests

from core.constants import BASE_URL


def check_backend_health() -> Dict[str, Any]:

    try:

        response = requests.get(
            f"{BASE_URL}/health",
            timeout=5
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return {}

        services = data.get("services")

        if not isinstance(services, dict):
            return {}

        return services

    except Exception:
        return {}