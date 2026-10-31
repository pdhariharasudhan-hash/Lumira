from app.core.lumira_core import LumiraCore


def test_understand_rejects_blank_request():
    result = LumiraCore().understand("")
    assert result["success"] is False
    assert result["current_stage"] == "validate"
