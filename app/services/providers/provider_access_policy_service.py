from __future__ import annotations

from typing import Any

from app.services.modes.ai_mode_service import AIModeService


class ProviderAccessDenied(PermissionError):
    """Raised before a provider call that violates the persisted AI mode."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class ProviderAccessPolicyService:
    """Fail-closed, centralized authorization for provider invocation boundaries.

    Providers must explicitly declare ``provider_scope`` as ``local`` or
    ``external``. Unknown or malformed scopes are treated as external.
    """

    LOCAL = "local"
    EXTERNAL = "external"

    def __init__(self, mode_service: Any | None = None) -> None:
        self.mode_service = mode_service or AIModeService()

    @staticmethod
    def provider_scope(provider: Any) -> str:
        try:
            scope = getattr(provider, "provider_scope", None)
        except Exception:
            return ProviderAccessPolicyService.EXTERNAL
        return scope if isinstance(scope, str) and scope in {ProviderAccessPolicyService.LOCAL, ProviderAccessPolicyService.EXTERNAL} else ProviderAccessPolicyService.EXTERNAL

    def authorize(self, provider: Any, capability: str = "provider operation") -> dict:
        if provider is None:
            raise ProviderAccessDenied("provider_unavailable", f"No provider is configured for {capability}.")
        try:
            policy = self.mode_service.get()
        except ValueError:
            raise ProviderAccessDenied("provider_policy_invalid", "Provider access is blocked because AI mode settings are invalid.") from None
        except Exception:
            raise ProviderAccessDenied("provider_policy_unavailable", "Provider access is blocked because AI mode settings could not be read safely.") from None
        if not isinstance(policy, dict):
            raise ProviderAccessDenied("provider_policy_unavailable", "Provider access is blocked because AI mode settings are invalid.")

        mode = policy.get("mode")
        scope = self.provider_scope(provider)
        if mode not in {"offline", "hybrid", "cloud"}:
            raise ProviderAccessDenied("provider_policy_invalid", "Provider access is blocked because the configured AI mode is invalid.")

        if scope == self.LOCAL:
            if mode == "cloud" or policy.get("local_providers_allowed") is not True:
                raise ProviderAccessDenied("local_provider_blocked", f"Local providers are not permitted in {mode.title()} mode.")
            return {"allowed": True, "mode": mode, "provider_scope": scope}

        # Cloud access requires a distinct, explicit opt-in in every mode.
        if mode == "offline" or policy.get("network_allowed") is not True or policy.get("external_providers_allowed") is not True or policy.get("cloud_enabled") is not True:
            raise ProviderAccessDenied("external_provider_consent_required", "External providers are blocked. Switch out of Offline mode and explicitly enable cloud provider access in Lumira settings.")
        return {"allowed": True, "mode": mode, "provider_scope": scope}
