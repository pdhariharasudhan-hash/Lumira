from fastapi import APIRouter, Query

from app.services.search.unified_search_service import (
    UnifiedSearchService
)

router = APIRouter()


@router.get(
    "/search"
)
def search(
    q: str = Query(min_length=1, max_length=500)
):

    results = (

        UnifiedSearchService()
        .search_all(
            q
        )
    )

    return {

        "success":
        True,

        "query":
        q,

        "results":
        results
    }
