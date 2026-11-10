import pytest

from app.services.providers.provider_access_policy_service import (
    ProviderAccessDenied,
    ProviderAccessPolicyService,
)


class ModeService:
    def __init__(self, mode, cloud_enabled=False):
        external = mode != "offline" and cloud_enabled is True
        self.policy = {
            "mode": mode,
            "cloud_enabled": cloud_enabled,
            "local_providers_allowed": mode != "cloud",
            "network_allowed": external,
            "external_providers_allowed": external,
        }

    def get(self):
        return dict(self.policy)


class LocalProvider:
    provider_scope = "local"


class ExternalProvider:
    provider_scope = "external"


class UnknownProvider:
    pass


@pytest.mark.parametrize("mode", ["offline", "hybrid"])
def test_local_provider_allowed_in_offline_and_hybrid(mode):
    policy = ProviderAccessPolicyService(ModeService(mode))
    assert policy.authorize(LocalProvider(), "chat")["provider_scope"] == "local"


def test_local_provider_blocked_in_cloud_mode():
    policy = ProviderAccessPolicyService(ModeService("cloud", True))
    with pytest.raises(ProviderAccessDenied) as error:
        policy.authorize(LocalProvider())
    assert error.value.code == "local_provider_blocked"


@pytest.mark.parametrize("mode", ["offline", "hybrid", "cloud"])
def test_external_provider_blocked_without_explicit_cloud_consent(mode):
    policy = ProviderAccessPolicyService(ModeService(mode, False))
    with pytest.raises(ProviderAccessDenied) as error:
        policy.authorize(ExternalProvider())
    assert error.value.code == "external_provider_consent_required"


def test_external_provider_allowed_only_with_explicit_consent_in_hybrid_and_cloud():
    for mode in ("hybrid", "cloud"):
        policy = ProviderAccessPolicyService(ModeService(mode, True))
        assert policy.authorize(ExternalProvider())["allowed"] is True


def test_unknown_provider_fails_closed_as_external():
    policy = ProviderAccessPolicyService(ModeService("hybrid", False))
    with pytest.raises(ProviderAccessDenied):
        policy.authorize(UnknownProvider())


def test_unreadable_mode_settings_fail_closed():
    class BrokenModeService:
        def get(self):
            raise OSError("private path")

    policy = ProviderAccessPolicyService(BrokenModeService())
    with pytest.raises(ProviderAccessDenied) as error:
        policy.authorize(LocalProvider())
    assert error.value.code == "provider_policy_unavailable"
