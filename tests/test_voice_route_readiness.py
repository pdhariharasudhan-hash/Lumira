from fastapi import HTTPException

from app.routes.voice_capture import _raise_for_voice_readiness


def test_missing_voice_provider_maps_to_service_unavailable():
    try:
        _raise_for_voice_readiness({
            "success": False,
            "code": "provider_unavailable",
            "message": "No speech provider is configured.",
        })
    except HTTPException as error:
        assert error.status_code == 503
        assert error.headers is None
    else:
        raise AssertionError("missing provider should return HTTP 503")


def test_resource_pressure_voice_deferral_is_retryable():
    try:
        _raise_for_voice_readiness({
            "success": False,
            "state": "deferred",
            "code": "resource_pressure_deferred",
            "message": "Transcription was deferred because memory is constrained.",
        })
    except HTTPException as error:
        assert error.status_code == 503
        assert error.headers["Retry-After"] == "30"
    else:
        raise AssertionError("resource-pressure deferral should return HTTP 503")


def test_non_readiness_voice_results_are_left_for_route_specific_handling():
    _raise_for_voice_readiness({"success": False, "code": "invalid_request"})


def test_wake_word_listener_denies_external_provider_before_starting():
    from app.services.providers.provider_access_policy_service import ProviderAccessDenied
    from app.services.voice.wake_word_listener_service import WakeWordListenerService

    class Provider:
        provider_scope = "external"

    class DenyPolicy:
        def authorize(self, provider, capability):
            raise ProviderAccessDenied("external_provider_consent_required", "External provider blocked.")

    service = WakeWordListenerService(Provider(), provider_policy=DenyPolicy())
    result = service.start()
    assert result["success"] is False
    assert result["code"] == "external_provider_consent_required"
    assert service.status()["listening"] is False


def test_provider_access_denial_maps_to_forbidden_http_response():
    try:
        _raise_for_voice_readiness({
            "success": False,
            "code": "external_provider_consent_required",
            "message": "External provider access requires consent.",
        })
    except HTTPException as error:
        assert error.status_code == 403
    else:
        raise AssertionError("provider access denial must map to HTTP 403")
