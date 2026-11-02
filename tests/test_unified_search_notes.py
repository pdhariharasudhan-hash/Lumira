from app.services.search.unified_search_service import UnifiedSearchService


def test_unified_search_empty_result_includes_notes():
    result = UnifiedSearchService().search_all("")
    assert "notes" in result
    assert result["notes"] == []


def test_unified_search_exposes_flat_items_for_empty_query():
    result = UnifiedSearchService().search_all("")
    assert "items" in result
    assert result["items"] == []
