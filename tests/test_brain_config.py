import pytest

from app.services.brain.brain_config import BrainConfig, ConfigurationError


def test_reads_only_lumira_namespace_and_returns_defaults():
    config = BrainConfig({"LUMIRA_MODE": "local", "OTHER_SECRET": "hidden"})
    assert config.get("LUMIRA_MODE") == "local"
    assert config.get("LUMIRA_MISSING", "safe") == "safe"
    assert config.snapshot() == {"LUMIRA_MODE": "local"}


@pytest.mark.parametrize("value", ["1", "true", "YES", "on", "enabled"])
def test_boolean_true_values(value):
    assert BrainConfig({"LUMIRA_FLAG": value}).get_bool("LUMIRA_FLAG") is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off", "disabled"])
def test_boolean_false_values(value):
    assert BrainConfig({"LUMIRA_FLAG": value}).get_bool("LUMIRA_FLAG", True) is False


def test_invalid_boolean_fails_closed_with_explicit_error():
    config = BrainConfig({"LUMIRA_FLAG": "sometimes"})
    with pytest.raises(ConfigurationError, match="boolean"):
        config.get_bool("LUMIRA_FLAG")


def test_integer_parsing_and_bounds():
    config = BrainConfig({"LUMIRA_WORKERS": "4"})
    assert config.get_int("LUMIRA_WORKERS", minimum=1, maximum=8) == 4
    with pytest.raises(ConfigurationError, match="minimum"):
        config.get_int("LUMIRA_WORKERS", minimum=5)
    with pytest.raises(ConfigurationError, match="integer"):
        BrainConfig({"LUMIRA_WORKERS": "4.5"}).get_int("LUMIRA_WORKERS")


def test_invalid_key_namespace_is_rejected():
    config = BrainConfig({})
    with pytest.raises(ConfigurationError, match="namespace"):
        config.get("PATH")
    with pytest.raises(ConfigurationError, match="namespace"):
        config.get("LUMIRA_bad-name")


def test_required_values_and_secret_access_are_explicit():
    config = BrainConfig({"LUMIRA_PROVIDER_API_KEY": "secret-value", "LUMIRA_PROVIDER": "local"})
    assert config.require("LUMIRA_PROVIDER") == "local"
    assert config.get_secret("LUMIRA_PROVIDER_API_KEY") == "secret-value"
    with pytest.raises(ConfigurationError, match="missing"):
        config.require("LUMIRA_MISSING")
    with pytest.raises(ConfigurationError, match="secret-designated"):
        config.get_secret("LUMIRA_PROVIDER")


def test_diagnostic_snapshot_redacts_secrets_and_is_detached():
    config = BrainConfig({"LUMIRA_API_KEY": "do-not-print", "LUMIRA_MODE": "local"})
    snapshot = config.snapshot()
    assert snapshot == {"LUMIRA_API_KEY": "[REDACTED]", "LUMIRA_MODE": "local"}
    snapshot["LUMIRA_MODE"] = "changed"
    assert config.get("LUMIRA_MODE") == "local"
    assert config.snapshot(redact_secrets=False)["LUMIRA_API_KEY"] == "do-not-print"


def test_reload_refreshes_process_environment_snapshot():
    source = {"LUMIRA_MODE": "first"}
    config = BrainConfig(source)
    source["LUMIRA_MODE"] = "second"
    source["LUMIRA_NEW_FLAG"] = "true"
    config.reload()
    assert config.get("LUMIRA_MODE") == "second"
    assert config.get_bool("LUMIRA_NEW_FLAG") is True


def test_non_string_environment_values_are_rejected():
    with pytest.raises(ConfigurationError, match="must be text"):
        BrainConfig({"LUMIRA_BAD": 123})


def test_secret_values_are_not_returned_by_default_snapshot():
    config = BrainConfig({"LUMIRA_TRANSCRIPTION_API_KEY": "test-secret"})
    assert "test-secret" not in repr(config.snapshot())
