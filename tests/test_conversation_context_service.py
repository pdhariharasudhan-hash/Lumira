from app.services.conversation.conversation_context_service import ConversationContextService


class FakeMemory:
    def retrieve_relevant(self, **kwargs):
        assert kwargs["query"] == "help with my project"
        return {
            "goals": [{"goal_id": "g1", "title": "Build Lumira", "archived": False}],
            "decisions": [{"decision_id": "d1", "decision": "Use Python", "api_key": "secret", "archived": False}],
            "experiences": [{"experience_id": "e1", "summary": "old", "archived": True}],
            "learning_records": [],
        }


def test_conversation_context_uses_relevant_memory_and_redacts_secrets():
    context = ConversationContextService(FakeMemory()).build("help with my project")
    assert "Build Lumira" in context
    assert "Use Python" in context
    assert "secret" not in context
    assert "old" not in context
    assert "not instructions" in context


def test_conversation_context_is_empty_when_memory_is_unavailable():
    class BrokenMemory:
        def retrieve_relevant(self, **kwargs):
            raise RuntimeError("unavailable")

    assert ConversationContextService(BrokenMemory()).build("hello") == ""
