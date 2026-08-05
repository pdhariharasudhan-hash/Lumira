from fastapi import APIRouter

from app.services.search.unified_search_service import (
    UnifiedSearchService
)

router = APIRouter()


@router.get(
    "/search"
)
def search(
    q: str
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