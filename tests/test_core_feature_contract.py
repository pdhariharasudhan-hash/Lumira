import tempfile
from pathlib import Path

from app.services.brain.brain_state import BrainState
from app.services.brain.brain_validator import BrainValidator
from app.services.features.core_feature_contract import CoreFeatureContract
from app.services.features.feature_registry_service import FeatureRegistryService


def _complete_state(contract):
    state = {field: {} for field in contract.REQUIRED_STATE_FIELDS}
    for field in contract.STRING_STATE_FIELDS:
        state[field] = ""
    state["status"] = "running"
    return state


def test_core_state_contract_requires_explicit_fields():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        contract = CoreFeatureContract(registry)

        result = contract.validate_state({"status": "running"})
        assert result["valid"] is False
        assert "goal" in result["missing"]
        assert "memory_reference" in result["missing"]


def test_core_state_contract_accepts_complete_state():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        contract = CoreFeatureContract(registry)

        state = _complete_state(contract)

        result = contract.validate_state(state)
        assert result["valid"] is True


def test_core_state_contract_rejects_unknown_status():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        contract = CoreFeatureContract(registry)

        state = _complete_state(contract)
        state["status"] = "guessing"

        result = contract.validate_state(state)
        assert result["valid"] is False
        assert result["invalid_status"] is True


def test_core_state_contract_rejects_non_string_status_without_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        contract = CoreFeatureContract(FeatureRegistryService(str(Path(tmp) / "features.json")))
        state = {field: None for field in contract.REQUIRED_STATE_FIELDS}
        state["status"] = ["running"]

        result = contract.validate_state(state)
        assert result["valid"] is False
        assert result["invalid_status"] is True
        assert result["status"] == "invalid"


def test_core_state_contract_rejects_malformed_string_fields():
    with tempfile.TemporaryDirectory() as tmp:
        contract = CoreFeatureContract(FeatureRegistryService(str(Path(tmp) / "features.json")))

        for field in contract.STRING_STATE_FIELDS:
            state = _complete_state(contract)
            state[field] = ["invalid"]
            result = contract.validate_state(state)
            assert result["valid"] is False
            assert field in result["invalid_fields"]


def test_core_state_contract_rejects_non_mapping_state_without_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        contract = CoreFeatureContract(FeatureRegistryService(str(Path(tmp) / "features.json")))

        result = contract.validate_state(["status", "running"])
        assert result["valid"] is False
        assert result["invalid_state_type"] is True
        assert "goal" in result["missing"]
        assert set(result["invalid_fields"]) == set(contract.STRING_STATE_FIELDS)


def test_brain_validator_rejects_runtime_corruption_of_mutable_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = BrainState()
    state.current_stage = ["invalid-after-construction"]

    result = BrainValidator().validate_state(state)

    assert result["valid"] is False
    assert "current_stage" in result["contract"]["invalid_fields"]


def test_feature_readiness_requires_activation_and_health():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FeatureRegistryService(str(Path(tmp) / "features.json"))
        contract = CoreFeatureContract(registry)

        result = contract.feature_ready("intent")
        assert result["ready"] is False
        assert result["enabled"] is False

        registry.enable("intent")
        result = contract.feature_ready("intent")
        assert result["ready"] is True


def test_core_state_contract_rejects_missing_or_null_status():
    with tempfile.TemporaryDirectory() as tmp:
        contract = CoreFeatureContract(FeatureRegistryService(str(Path(tmp) / "features.json")))
        state = _complete_state(contract)
        state["status"] = None

        result = contract.validate_state(state)
        assert result["valid"] is False
        assert result["invalid_status"] is True


def test_feature_readiness_rejects_enabled_feature_with_missing_dependency(tmp_path):
    registry = FeatureRegistryService(str(tmp_path / "features.json"))
    assert registry.enable("projects")[0] is True
    assert registry.enable("code")[0] is True

    persisted = registry.get_all()
    persisted["projects"]["status"] = "DISABLED"
    persisted["projects"]["enabled"] = False
    registry.store.write(persisted)

    result = CoreFeatureContract(registry).feature_ready("code")
    assert result["ready"] is False
    assert any("projects" in blocker for blocker in result["blockers"])


def test_feature_readiness_rejects_invalid_feature_name():
    with tempfile.TemporaryDirectory() as tmp:
        contract = CoreFeatureContract(FeatureRegistryService(str(Path(tmp) / "features.json")))

        result = contract.feature_ready(["intent"])
        assert result["ready"] is False
        assert result["reason"] == "invalid_feature_name"
