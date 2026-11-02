from app.services.workflow_recovery.checkpoint_resume_adapter_service import CheckpointResumeAdapterService

class FakeOrchestrator:
    def __init__(self, allowed):
        self.allowed = allowed
    def prepare(self, *args, **kwargs):
        return {"gate": {"execute_resume": self.allowed}}

class FakeEngine:
    def __init__(self):
        self.calls = 0
    def resume(self, run_id):
        self.calls += 1
        return {"success": True, "state": "completed", "run_id": run_id}

def test_blocked_checkpoint_never_reaches_workflow_engine():
    engine = FakeEngine()
    service = CheckpointResumeAdapterService(FakeOrchestrator(False), engine)
    result = service.resume("session-1", {"run_id": "run-1"}, "request-1")
    assert result["success"] is False
    assert engine.calls == 0

def test_valid_checkpoint_reaches_existing_resume_engine():
    engine = FakeEngine()
    service = CheckpointResumeAdapterService(FakeOrchestrator(True), engine)
    result = service.resume("session-1", {"run_id": "run-1"}, "request-1")
    assert result["success"] is True
    assert engine.calls == 1
