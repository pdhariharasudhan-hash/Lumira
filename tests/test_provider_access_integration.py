from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.image.image_generation_service import ImageGenerationService
from app.services.image.image_understanding_service import ImageUnderstandingService
from app.services.research.research_capability_service import ResearchCapabilityService
from app.services.response.summary_service import SummaryService
from app.services.voice.transcript_service import TranscriptService
from app.services.voice.voice_interaction_service import SpeechPlaybackService, WakeWordActivationService
from app.services.providers.provider_access_policy_service import ProviderAccessPolicyService
from app.services.resources.resource_budget_service import ResourceBudgetService


class ExternalNeverCalled:
    provider_scope = "external"

    def __init__(self):
        self.calls = 0

    def generate(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def analyze(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def research(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def summarize(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def transcribe(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def synthesize(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")

    def detect(self, *args):
        self.calls += 1
        raise AssertionError("blocked provider must never be invoked")


class OfflineMode:
    def get(self):
        return {
            "mode": "offline",
            "cloud_enabled": False,
            "local_providers_allowed": True,
            "network_allowed": False,
            "external_providers_allowed": False,
        }


def test_offline_denies_external_provider_before_every_modality_invocation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ResourceBudgetService, "execution_guidance", lambda self: {
        "resource_pressure": "normal", "defer_optional_heavy_media_work": False,
    })
    artifacts = ArtifactManagerService()
    audio = artifacts.create_binary_artifact("audio", b"RIFF\x00\x00\x00\x00WAVE", "test", "wav")
    transcript = artifacts.create_artifact("transcripts", "transcript", "test", "txt")
    policy = ProviderAccessPolicyService(OfflineMode())

    cases = [
        (ExternalNeverCalled(), lambda provider: ImageGenerationService(provider, provider_policy=policy).generate("test"), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: ImageUnderstandingService(provider, provider_policy=policy).analyze(b"\x89PNG\r\n\x1a\nvalid"), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: ResearchCapabilityService(provider, provider_policy=policy).web_research("test"), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: TranscriptService(provider, provider_policy=policy).generate_transcript(audio["artifact_id"]), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: SummaryService(provider, provider_policy=policy).generate_summary(transcript["artifact_id"]), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: SpeechPlaybackService(provider, provider_policy=policy).play("hello"), "external_provider_consent_required"),
        (ExternalNeverCalled(), lambda provider: WakeWordActivationService(provider, provider_policy=policy).activate(audio["artifact_id"]), "external_provider_consent_required"),
    ]
    for provider, invoke, expected_code in cases:
        result = invoke(provider)
        assert result["success"] is False
        assert result["code"] == expected_code
        assert provider.calls == 0


def test_unknown_provider_is_treated_as_external_even_with_no_scope():
    class UnknownProvider:
        pass

    policy = ProviderAccessPolicyService(OfflineMode())
    assert policy.provider_scope(UnknownProvider()) == "external"
