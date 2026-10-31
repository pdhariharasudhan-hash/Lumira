from app.services.system.personal_ai_status_service import PersonalAIStatusService

def test_status_service_has_expected_top_level_shape(monkeypatch):
    class Artifacts:
        def availability_summary(self): return {"total": 1, "available": 1, "unavailable": 0}
    class Features:
        def list_features(self): return {"count": 2, "enabled": ["a"], "available": ["b"], "failed": []}
    class Notes:
        def note_summary(self): return {"total": 3, "with_content": 2}
    class Research:
        def summary(self): return {"total": 4}
    class Recovery:
        def list_recent(self, limit): return []

    import app.services.system.personal_ai_status_service as module
    monkeypatch.setattr(module, "ArtifactManagerService", Artifacts)
    monkeypatch.setattr(module, "FeatureRegistryService", Features)
    monkeypatch.setattr(module, "NotepadService", Notes)
    monkeypatch.setattr(module, "ResearchLibraryService", Research)
    monkeypatch.setattr(module, "RecoveryCheckpointService", Recovery)
    result = PersonalAIStatusService().snapshot()
    assert result["knowledge"]["notes"]["total"] == 3
    assert result["features"]["enabled"] == 1
