import pytest

from app.services.conversation.conversation_provider_router import (
    ConversationProviderRouter,
    ConversationProviderUnavailable,
)


class ModeService:
    def __init__(self, mode, cloud_enabled=False):
        self.policy = {
            "mode": mode,
            "cloud_enabled": cloud_enabled,
            "local_providers_allowed": mode != "cloud",
            "network_allowed": mode != "offline" and cloud_enabled is True,
            "external_providers_allowed": mode != "offline" and cloud_enabled is True,
        }

    def get(self):
        return dict(self.policy)


class LocalProvider:
    provider_scope = "local"
    def __init__(self, result="local answer", error=None):
        self.result = result
        self.error = error
        self.calls = []

    def chat(self, message, history=None):
        self.calls.append((message, history))
        if self.error:
            raise self.error
        return self.result


class CloudProvider:
    provider_scope = "external"
    def __init__(self, result="cloud answer"):
        self.result = result
        self.calls = []

    def chat(self, message, history=None):
        self.calls.append((message, history))
        return self.result


def test_hybrid_uses_local_first_and_does_not_call_cloud():
    local = LocalProvider()
    cloud = CloudProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("hybrid", False),
        local_provider_factory=lambda: local,
        cloud_provider_factory=lambda: cloud,
    )
    assert router.chat("hello") == "local answer"
    assert len(local.calls) == 1
    assert cloud.calls == []


def test_hybrid_falls_back_to_cloud_only_after_explicit_consent():
    local = LocalProvider(error=RuntimeError("local offline"))
    cloud = CloudProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("hybrid", True),
        local_provider_factory=lambda: local,
        cloud_provider_factory=lambda: cloud,
    )
    assert router.chat("hello") == "cloud answer"
    assert len(cloud.calls) == 1


def test_hybrid_without_cloud_consent_never_calls_cloud():
    local = LocalProvider(error=RuntimeError("local offline"))
    cloud = CloudProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("hybrid", False),
        local_provider_factory=lambda: local,
        cloud_provider_factory=lambda: cloud,
    )
    with pytest.raises(ConversationProviderUnavailable) as error:
        router.chat("hello")
    assert error.value.code == "local_provider_unavailable"
    assert cloud.calls == []


def test_cloud_mode_requires_explicit_consent():
    cloud = CloudProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("cloud", False),
        cloud_provider_factory=lambda: cloud,
    )
    with pytest.raises(ConversationProviderUnavailable) as error:
        router.chat("hello")
    assert error.value.code == "cloud_consent_required"
    assert cloud.calls == []


def test_offline_mode_never_falls_back_to_cloud_even_if_consent_was_saved():
    local = LocalProvider(error=RuntimeError("local offline"))
    cloud = CloudProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("offline", True),
        local_provider_factory=lambda: local,
        cloud_provider_factory=lambda: cloud,
    )
    with pytest.raises(ConversationProviderUnavailable):
        router.chat("hello")
    assert cloud.calls == []


def test_offline_mode_blocks_unknown_provider_before_chat_call():
    class UnknownProvider:
        def __init__(self):
            self.calls = []
        def chat(self, message, history=None):
            self.calls.append(message)
            return "must not run"

    provider = UnknownProvider()
    router = ConversationProviderRouter(
        mode_service=ModeService("offline", False),
        local_provider_factory=lambda: provider,
    )
    with pytest.raises(ConversationProviderUnavailable) as error:
        router.chat("hello")
    assert error.value.code == "external_provider_consent_required"


def test_provider_malformed_chat_response_is_rejected():
    class Mode:
        def get(self):
            return {
                "mode": "offline",
                "cloud_enabled": False,
                "local_providers_allowed": True,
                "network_allowed": False,
                "external_providers_allowed": False,
            }

    class Provider:
        provider_scope = "local"

        def chat(self, message, **kwargs):
            return None

    router = ConversationProviderRouter(
        mode_service=Mode(),
        local_provider_factory=lambda: Provider(),
    )
    with pytest.raises(ConversationProviderUnavailable) as error:
        router.chat("hello")
    assert error.value.code == "provider_invalid_response"
from app.services.conversation.conversation_provider_router import ConversationProviderRouter


def test_router_passes_relevant_context_to_a_context_capable_provider():
    class Mode:
        def get(self):
            return {"mode": "hybrid", "cloud_enabled": False}

    class Policy:
        def authorize(self, provider, purpose):
            assert purpose == "chat"

    class Provider:
        provider_scope = "local"
        def __init__(self): self.received = None
        def chat(self, message, history=None, context=None):
            self.received = context
            return "ok"

    provider = Provider()
    router = ConversationProviderRouter(
        mode_service=Mode(),
        local_provider_factory=lambda: provider,
        provider_policy=Policy(),
    )
    assert router.chat("hello", context="remembered project fact") == "ok"
    assert provider.received == "remembered project fact"
