from app.services.creator.creator_os_service import CreatorOSService
from app.services.providers.provider_registry import ProviderRegistry


def test_audio_generation_saves_validated_binary_artifact(monkeypatch):
    class FakeProvider:
        provider_scope = "local"
        def synthesize(self, text, language):
            return {"success": True, "content": b"ID3fake-mp3", "extension": "mp3"}

    class FakePolicy:
        def authorize(self, provider, purpose):
            assert purpose == "creator audio generation"

    class FakeArtifacts:
        def create_binary_artifact(self, artifact_type, content, source, extension):
            assert (artifact_type, content, extension) == ("audio", b"ID3fake-mp3", "mp3")
            return {"artifact_id": "audio-1", "type": "audio"}

    import app.services.providers.provider_access_policy_service as policy
    monkeypatch.setattr(policy, "ProviderAccessPolicyService", FakePolicy)
    ProviderRegistry.register("speech_synthesis", FakeProvider())
    try:
        result = CreatorOSService(FakeArtifacts()).synthesize_audio("Hello", "en")
    finally:
        ProviderRegistry.unregister("speech_synthesis")
    assert result["success"] is True
    assert result["artifact"]["artifact_id"] == "audio-1"


def test_audio_generation_reports_missing_provider():
    ProviderRegistry.unregister("speech_synthesis")
    result = CreatorOSService().synthesize_audio("Hello", "en")
    assert result["success"] is False
    assert result["code"] == "speech_provider_unavailable"
