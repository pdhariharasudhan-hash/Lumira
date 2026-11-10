from __future__ import annotations

from app.services.modes.ai_mode_service import AIModeService
from app.services.providers.ollama_chat_provider import OllamaChatProvider
from app.services.providers.openai_compatible_chat_provider import OpenAICompatibleChatProvider
from app.services.providers.provider_access_policy_service import ProviderAccessDenied, ProviderAccessPolicyService


class ConversationProviderUnavailable(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.user_message = message


class ConversationProviderRouter:
    """Apply the persisted local/cloud policy to normal assistant conversations."""

    def __init__(
        self,
        *,
        mode_service=None,
        local_provider_factory=None,
        cloud_provider_factory=None,
        provider_policy=None,
    ):
        self.mode_service = mode_service or AIModeService()
        self.local_provider_factory = local_provider_factory or OllamaChatProvider
        self.cloud_provider_factory = cloud_provider_factory or OpenAICompatibleChatProvider
        self.provider_policy = provider_policy or ProviderAccessPolicyService(self.mode_service)

    def chat(self, message: str, history=None, context: str | None = None) -> str:
        try:
            policy = self.mode_service.get()
        except ValueError:
            raise ConversationProviderUnavailable("provider_policy_invalid", "Provider access is blocked because AI mode settings are invalid.") from None
        except Exception:
            raise ConversationProviderUnavailable("provider_policy_unavailable", "Provider access is blocked because AI mode settings could not be read safely.") from None
        mode = policy["mode"]
        cloud_enabled = policy["cloud_enabled"]

        if mode == "cloud":
            if not cloud_enabled:
                raise ConversationProviderUnavailable(
                    "cloud_consent_required",
                    "Cloud mode is selected, but cloud providers are disabled. Enable cloud use explicitly in Lumira settings first.",
                )
            return self._validated_chat(self._cloud_chat(message, history, context))

        try:
            local_provider = self.local_provider_factory()
            self.provider_policy.authorize(local_provider, "chat")
            return self._validated_chat(self._provider_chat(local_provider, message, history, context))
        except ProviderAccessDenied as error:
            raise ConversationProviderUnavailable(error.code, error.user_message) from None
        except ConversationProviderUnavailable:
            raise
        except Exception:
            if mode == "hybrid" and cloud_enabled:
                return self._validated_chat(self._cloud_chat(message, history, context))
            raise ConversationProviderUnavailable(
                "local_provider_unavailable",
                "No local chat model is available. Start and configure Ollama, or explicitly enable cloud providers and configure a cloud chat provider.",
            ) from None

    @staticmethod
    def _provider_chat(provider, message: str, history=None, context: str | None = None) -> str:
        kwargs = {"history": history}
        if isinstance(context, str) and context.strip():
            kwargs["context"] = context
        return provider.chat(message, **kwargs)

    @staticmethod
    def _validated_chat(response) -> str:
        if not isinstance(response, str) or not response.strip():
            raise ConversationProviderUnavailable(
                "provider_invalid_response",
                "The configured chat provider returned no usable text response.",
            )
        return response.strip()

    def _cloud_chat(self, message: str, history=None, context: str | None = None) -> str:
        try:
            provider = self.cloud_provider_factory()
            self.provider_policy.authorize(provider, "cloud chat")
            return self._validated_chat(self._provider_chat(provider, message, history, context))
        except ProviderAccessDenied as error:
            raise ConversationProviderUnavailable(error.code, error.user_message) from None
        except ConversationProviderUnavailable:
            raise
        except Exception:
            raise ConversationProviderUnavailable(
                "cloud_provider_unavailable",
                "Cloud use is enabled, but the configured cloud chat provider is unavailable. Check its endpoint, model and credentials.",
            ) from None
