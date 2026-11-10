from app.services.capabilities.phase_zero_capability_service import PhaseZeroCapabilityService


def test_phase_zero_inventory_preserves_99_capability_denominator_without_false_verification():
    service = PhaseZeroCapabilityService()
    summary = service.summary()
    entries = service.inventory()

    assert summary["total"] == 99
    assert len(entries) == 99
    assert summary["verified"] > 0
    assert summary["progress_percent"] == round(summary["verified"] / 99 * 100, 2)
    assert summary["counts"]["BLOCKED"] > 0
    assert any(item["evidence"] for item in entries)
    assert all(
        item["status"] == "VERIFIED"
        for item in entries
        if item["capability"] in {
            "Natural-language understanding",
            "Multi-model management",
        }
    )


def test_security_capabilities_remain_tested_until_full_acceptance():
    entries = PhaseZeroCapabilityService().inventory()
    by_name = {item["capability"]: item for item in entries}

    assert by_name["Threat and unsafe-operation detection"]["status"] == "TESTED"
    assert by_name["Security monitoring and audit logging"]["status"] == "TESTED"
    assert by_name["Speech generation"]["status"] == "TESTED"
    assert "tests/test_windows_sapi_speech_provider.py" in by_name["Speech generation"]["evidence"]
    assert "tests/test_security_audit_log.py" in by_name["Security monitoring and audit logging"]["evidence"]


def test_capabilities_without_complete_semantic_acceptance_are_not_overstated():
    entries = PhaseZeroCapabilityService().inventory()
    by_name = {item["capability"]: item for item in entries}
    assert by_name["Tool selection"]["status"] == "VERIFIED"
    assert "tests/test_agent_command_integration.py" in by_name["Tool selection"]["evidence"]

    awaiting_integration = {
        "Memory evolution",
        "Agent collaboration",
        "Agent communication",
        "Agent optimization",
        "Agent self-evaluation",
        "Workflow optimization",
        "Trend analysis",
        "Knowledge graph",
        "Skill acquisition",
        "Knowledge improvement",
    }
    assert all(by_name[name]["status"] == "TESTED" for name in awaiting_integration)
    for name in {
        "Agent collaboration",
        "Agent communication",
        "Agent optimization",
        "Agent self-evaluation",
    }:
        assert "tests/test_agent_collaboration.py" in by_name[name]["evidence"]
