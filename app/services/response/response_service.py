from typing import Any, Dict


def build_structured_response(endpoint: str, status: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": status == "ok",
        "endpoint": endpoint,
        "status": status,
        "data": data
    }
    