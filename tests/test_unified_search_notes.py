from app.services.search.unified_search_service import UnifiedSearchService


def test_unified_search_empty_result_includes_notes():
    result = UnifiedSearchService().search_all("")
    assert "notes" in result
    assert result["notes"] == []
