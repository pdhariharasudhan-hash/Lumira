from fastapi import APIRouter, Query
from typing import Annotated

from app.services.search.unified_search_service import (
    UnifiedSearchService
)

router = APIRouter()


def _hide_internal_paths(value):
    """Remove local filesystem paths from nested search results."""
    if isinstance(value, dict):
        return {
            key: _hide_internal_paths(item)
            for key, item in value.items()
            if key != "file"
        }
    if isinstance(value, list):
        return [_hide_internal_paths(item) for item in value]
    return value


@router.get(
    "/search"
)
def search(
    q: Annotated[str, Query(min_length=1, max_length=500)]
):

    normalized_query = q.strip()
    if not normalized_query:
        return {"success": True, "query": "", "results": []}

    results = UnifiedSearchService().search_all(normalized_query)
    # Keep the public search response aligned with artifact APIs: never expose
    # internal filesystem paths, including when they are nested in result data.
    results = _hide_internal_paths(results)

    return {
        "success": True,
        "query": normalized_query,
        "results": results,
    }
