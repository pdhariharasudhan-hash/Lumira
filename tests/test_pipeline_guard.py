from types import SimpleNamespace
from app.services.brain.pipeline_guard import PipelineGuard


def test_verification_guard_allows_ready_state():
    state = SimpleNamespace(verification=SimpleNamespace(ready_for_execution=True, passed_checks=["ok"], failed_checks=[], warnings=[]), verification_result=None)
    assert PipelineGuard.should_stop("verification", state) is False
    assert state.verification_result["ready_for_execution"] is True


def test_verification_guard_stops_failed_state():
    state = SimpleNamespace(verification=SimpleNamespace(ready_for_execution=False, passed_checks=[], failed_checks=["plan"], warnings=[]), verification_result=None)
    assert PipelineGuard.should_stop("verification", state) is True
    assert state.verification_result["failed_checks"] == ["plan"]
