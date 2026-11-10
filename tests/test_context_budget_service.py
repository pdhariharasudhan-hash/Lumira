from app.services.conversation.context_budget_service import ContextBudgetService


def test_context_budget_keeps_newest_messages_when_older_history_is_too_large():
    history = [
        {"role": "user", "content": "old " * 1500},
        {"role": "assistant", "content": "old answer " * 1200},
        {"role": "user", "content": "newest question"},
        {"role": "assistant", "content": "newest answer"},
    ]

    selected = ContextBudgetService.select_recent_history(
        history, max_messages=12, max_chars=300, max_tokens=300
    )

    assert selected == history[-2:]


def test_context_budget_preserves_chronological_order():
    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]
    selected = ContextBudgetService.select_recent_history(
        history, max_messages=2, max_chars=100, max_tokens=100
    )
    assert [item["content"] for item in selected] == ["two", "three"]


def test_context_budget_ignores_invalid_messages_and_enforces_limits():
    history = [
        {"role": "system", "content": "not forwarded"},
        {"role": "user", "content": "x" * 5000},
        {"role": "assistant", "content": "valid"},
    ]
    selected = ContextBudgetService.select_recent_history(
        history, max_messages=1, max_chars=100, max_tokens=100
    )
    assert selected == [{"role": "assistant", "content": "valid"}]
from app.services.conversation.context_budget_service import ContextBudgetService
from app.services.providers.ollama_chat_provider import OllamaChatProvider
from app.services.providers.openai_compatible_chat_provider import OpenAICompatibleChatProvider


def test_both_chat_providers_keep_newest_context_in_order():
    history = [
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer"},
        {"role": "user", "content": "newer question"},
        {"role": "assistant", "content": "newer answer"},
    ]
    expected = ContextBudgetService.select_recent_history(
        history, max_messages=2, max_chars=1000, max_tokens=1000
    )
    assert OllamaChatProvider._history(history) == history[-12:]
    assert OpenAICompatibleChatProvider._history(history) == history[-12:]
    assert expected == history[-2:]


def test_provider_history_does_not_drop_newest_messages_after_large_old_turns():
    history = [
        {"role": "user", "content": "old " * 3500},
        {"role": "assistant", "content": "old response " * 1000},
        {"role": "user", "content": "latest question"},
        {"role": "assistant", "content": "latest answer"},
    ]
    for provider in (OllamaChatProvider, OpenAICompatibleChatProvider):
        selected = provider._history(history)
        assert selected[-2:] == history[-2:]
