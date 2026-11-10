from __future__ import annotations

import os
import sys

import pytest

from app.services.resources.resource_budget_service import ResourceBudgetService


@pytest.mark.skipif(os.name == "nt", reason="procfs fallback is Linux/WSL-specific")
def test_resource_budget_reads_procfs_when_psutil_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)

    snapshot = ResourceBudgetService().snapshot()

    assert snapshot["memory"]["available"] is True
    assert snapshot["memory"]["source"] == "proc_meminfo"
    assert snapshot["memory"]["total_gib"] > 0
    assert 0 <= snapshot["memory"]["available_gib"] <= snapshot["memory"]["total_gib"]
    assert snapshot["resource_pressure"] in {"critical", "constrained", "normal"}
from app.services.resources.resource_budget_service import ResourceBudgetService


def test_execution_guidance_exposes_all_consumer_policy_fields():
    guidance = ResourceBudgetService().execution_guidance()
    assert guidance["resource_profile"] in {"low_memory", "standard"}
    assert guidance["resource_pressure"] in {"critical", "constrained", "normal", "unknown"}
    assert isinstance(guidance["defer_optional_heavy_media_work"], bool)
    assert guidance["max_concurrent_local_model_requests"] >= 1
