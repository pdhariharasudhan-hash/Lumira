from __future__ import annotations

from typing import Any


_SYSTEMS = (
    ("Main Brain", ("Natural-language understanding", "Goal understanding", "Autonomous decision-making", "Intelligent orchestration", "Complex problem-solving", "Self-evaluation")),
    ("Intelligence Engine", ("Multi-model management", "Provider management", "Context optimization", "Intelligent model routing", "Tool selection", "Structured reasoning and output")),
    ("Memory Engine", ("Episodic memory", "Semantic memory", "Personal knowledge memory", "Long-term memory", "Memory prioritization", "Memory consolidation", "Memory evolution")),
    ("Voice Intelligence", ("Wake-word detection", "Continuous voice interaction", "Voice activity detection", "Multilingual speech recognition", "Speech generation", "Speaker recognition", "Voice conversation management")),
    ("Autonomous Agent Engine", ("Specialized agent creation", "Dynamic agent allocation", "Agent collaboration", "Agent communication", "Agent optimization", "Agent self-evaluation")),
    ("Workflow Engine", ("Dynamic task decomposition", "Workflow scheduling", "Dependency management", "Conditional execution", "Long-running workflow management", "Workflow optimization")),
    ("Research Engine", ("Deep research", "Multi-source investigation", "Evidence verification", "Information extraction", "Trend analysis", "Knowledge graph")),
    ("Creation Studio", ("Image generation", "Video generation", "Audio generation", "Original music generation", "Diagram generation", "Blueprint and schematic generation", "3D model generation", "Presentation and document generation")),
    ("Development Studio", ("Autonomous software development", "Code generation", "Application generation", "Website generation", "Database generation and management", "API generation and integration", "Debugging and optimization", "Git, build, testing, and deployment management")),
    ("Learning Engine", ("Experience-based learning", "Adaptive workflow improvement", "User preference learning", "Performance optimization", "Skill acquisition", "Knowledge improvement")),
    ("Personal Assistant", ("Calendar management", "Email management", "Scheduling and reminders", "Personal finance assistance", "File and document management", "Notifications and alerts", "Productivity and task management")),
    ("Desktop Intelligence", ("Windows application control", "Desktop automation", "Application interaction", "File operations", "Process and resource management", "Desktop observation and understanding", "Desktop task execution and recovery")),
    ("Security Intelligence", ("Permission management", "Autonomous action policy", "Sandboxing and isolation", "Secrets and credential protection", "Threat and unsafe-operation detection", "Security monitoring and audit logging")),
    ("Device Intelligence", ("Universal supported-device communication", "ESP32 integration", "Raspberry Pi integration", "Sensor and actuator integration, including supported IoT automation")),
    ("Robotics Intelligence", ("Robot vision", "Object recognition", "Environmental perception", "Navigation", "Obstacle avoidance", "Motion planning", "Robotic arm control", "Object manipulation", "Multi-robot coordination")),
)

_BLOCKED = {
    "Wake-word detection", "Continuous voice interaction", "Voice activity detection",
    "Speech generation", "Speaker recognition", "Video generation", "Audio generation",
    "Original music generation", "3D model generation", "Calendar management",
    "Email management", "Windows application control", "Desktop automation",
    "Application interaction", "Desktop observation and understanding",
    "ESP32 integration", "Raspberry Pi integration", "Robot vision", "Object recognition",
    "Environmental perception", "Navigation", "Obstacle avoidance", "Motion planning",
    "Robotic arm control", "Object manipulation", "Multi-robot coordination",
}

_NOT_STARTED = {
    "Knowledge graph", "Trend analysis", "Personal finance assistance",
    "Speaker recognition", "Threat and unsafe-operation detection",
}

_MAIN_BRAIN_EVIDENCE = {
    "Natural-language understanding": (
        "TESTED",
        ["tests/test_pipeline.py", "tests/test_validation.py"],
    ),
    "Goal understanding": (
        "TESTED",
        ["tests/test_pipeline.py", "app/services/goals/goal_module.py"],
    ),
    "Autonomous decision-making": (
        "TESTED",
        ["tests/test_verification_service.py", "tests/test_brain_execution_coordinator.py"],
    ),
    "Intelligent orchestration": (
        "TESTED",
        ["tests/test_brain_execution_coordinator.py", "app/services/brain/brain_service.py"],
    ),
}

_MILESTONE_EVIDENCE = {
    "Natural-language understanding": ("VERIFIED", ["tests/test_pipeline.py", "tests/test_validation.py"]),
    "Goal understanding": ("VERIFIED", ["tests/test_pipeline.py", "tests/test_memory_lifecycle.py"]),
    "Autonomous decision-making": ("VERIFIED", ["tests/test_verification_service.py", "tests/test_brain_execution_coordinator.py"]),
    "Intelligent orchestration": ("VERIFIED", ["tests/test_brain_execution_coordinator.py", "tests/test_brain_agent_orchestrator.py"]),
    "Multi-model management": ("VERIFIED", ["tests/test_multi_model_orchestrator.py"]),
    "Provider management": ("VERIFIED", ["tests/test_multi_model_orchestrator.py", "tests/test_provider_boundaries.py"]),
    "Context optimization": ("VERIFIED", ["tests/test_pipeline.py", "tests/test_intelligence_routes.py"]),
    "Intelligent model routing": ("VERIFIED", ["tests/test_multi_model_orchestrator.py"]),
    "Structured reasoning and output": ("VERIFIED", ["tests/test_pipeline.py", "tests/test_intelligence_batch.py"]),
    "Episodic memory": ("VERIFIED", ["tests/test_memory_lifecycle.py"]),
    "Semantic memory": ("VERIFIED", ["tests/test_memory_lifecycle.py"]),
    "Personal knowledge memory": ("VERIFIED", ["tests/test_memory_lifecycle.py"]),
    "Long-term memory": ("VERIFIED", ["tests/test_memory_lifecycle.py", "tests/test_validation.py"]),
    "Memory prioritization": ("VERIFIED", ["tests/test_memory_lifecycle.py"]),
    "Memory consolidation": ("VERIFIED", ["tests/test_memory_lifecycle.py"]),
    "Multilingual speech recognition": ("TESTED", ["tests/test_voice_interactions.py"]),
    "Speech generation": ("TESTED", ["tests/test_windows_sapi_speech_provider.py", "tests/test_windows_sapi_provider_registration.py", "app/services/providers/windows_sapi_speech_provider.py"]),
    "Voice conversation management": ("TESTED", ["tests/test_voice_interactions.py"]),
    "Specialized agent creation": ("VERIFIED", ["tests/test_agents.py"]),
    "Dynamic agent allocation": ("VERIFIED", ["tests/test_agents.py", "tests/test_brain_agent_orchestrator.py"]),
    "Dynamic task decomposition": ("VERIFIED", ["tests/test_workflow_agent_execution.py", "tests/test_pipeline.py"]),
    "Workflow scheduling": ("VERIFIED", ["tests/test_modes_workflows.py", "tests/test_workflow_agent_execution.py"]),
    "Dependency management": ("VERIFIED", ["tests/test_modes_workflows.py", "tests/test_workflow_insights.py"]),
    "Conditional execution": ("VERIFIED", ["tests/test_workflow_agent_execution.py"]),
    "Long-running workflow management": ("VERIFIED", ["tests/test_run_recovery.py", "tests/test_workflow_recovery_intelligence.py"]),
    "Deep research": ("VERIFIED", ["tests/test_research.py"]),
    "Multi-source investigation": ("VERIFIED", ["tests/test_research.py", "tests/test_research_library_service.py"]),
    "Evidence verification": ("VERIFIED", ["tests/test_research.py"]),
    "Information extraction": ("VERIFIED", ["tests/test_research.py"]),
    "Image generation": ("TESTED", ["tests/test_generator_artifacts.py", "tests/test_image_generation_resource_budget.py"]),
    "Diagram generation": ("VERIFIED", ["tests/test_modes_workflows.py", "tests/test_generator_artifacts.py"]),
    "Blueprint and schematic generation": ("VERIFIED", ["tests/test_modes_workflows.py", "tests/test_generator_artifacts.py"]),
    "Presentation and document generation": ("VERIFIED", ["tests/test_modes_workflows.py", "tests/test_generator_artifacts.py"]),
    "Autonomous software development": ("TESTED", ["tests/test_autonomous_development.py", "tests/test_development_backlog.py"]),
    "Code generation": ("VERIFIED", ["tests/test_generation.py", "tests/test_project_pipeline_capability.py"]),
    "Application generation": ("VERIFIED", ["tests/test_generation.py"]),
    "Website generation": ("VERIFIED", ["tests/test_generation.py"]),
    "Automated debugging and optimization": ("VERIFIED", ["tests/test_autonomous_development.py"]),
    "Git, build, testing, and deployment management": ("TESTED", ["tests/test_autonomous_development.py", "tests/test_development_backlog.py"]),
    "Experience-based learning": ("VERIFIED", ["tests/test_memory_lifecycle.py", "tests/test_outcome_learning_features.py"]),
    "Adaptive workflow improvement": ("VERIFIED", ["tests/test_outcome_learning_features.py", "tests/test_intelligence_batch.py"]),
    "User preference learning": ("TESTED", ["tests/test_persistence.py", "tests/test_intelligence_routes.py"]),
    "Performance optimization": ("TESTED", ["tests/test_image_generation_resource_budget.py", "tests/test_speech_resource_budget.py"]),
    "Trend analysis": ("TESTED", ["tests/test_research_library_service.py", "app/routes/research_library.py"]),
    "Knowledge graph": ("TESTED", ["tests/test_research_library_service.py", "app/routes/research_library.py"]),
    "Memory evolution": ("TESTED", ["tests/test_memory_lifecycle.py"]),
    "Agent collaboration": (
        "TESTED",
        ["tests/test_agent_collaboration.py", "tests/test_agents.py", "app/routes/agents.py", "app/agents/agent_collaboration_service.py"],
    ),
    "Agent communication": (
        "TESTED",
        ["tests/test_agent_collaboration.py", "app/routes/agents.py", "app/agents/agent_collaboration_service.py"],
    ),
    "Agent self-evaluation": (
        "TESTED",
        ["tests/test_agent_collaboration.py", "app/routes/agents.py", "app/agents/agent_collaboration_service.py"],
    ),
    "Tool selection": (
        "VERIFIED",
        [
            "tests/test_tool_selection.py",
            "tests/test_brain_agent_orchestrator.py",
            "tests/test_agent_command_integration.py",
            "tests/test_agents.py",
            "app/agents/agent_manager.py",
            "app/services/multi_model/multi_model_orchestrator.py",
        ],
    ),
    "Workflow optimization": ("TESTED", ["tests/test_workflow_optimization.py", "app/agents/workflow_engine.py"]),
    "Complex problem-solving": ("VERIFIED", ["tests/test_brain_execution_coordinator.py", "tests/test_workflow_agent_execution.py"]),
    "Self-evaluation": ("VERIFIED", ["tests/test_pipeline.py", "tests/test_brain_execution_control.py"]),
    "Agent optimization": (
        "TESTED",
        ["tests/test_agent_collaboration.py", "app/routes/agents.py", "app/agents/agent_collaboration_service.py"],
    ),
    "Skill acquisition": ("TESTED", ["tests/test_learning_evolution.py", "app/services/learning/learning_evolution_service.py"]),
    "Knowledge improvement": ("TESTED", ["tests/test_learning_evolution.py", "app/routes/outcome_learning.py"]),
    "Threat and unsafe-operation detection": ("TESTED", [
        "tests/test_unsafe_operation_detection.py",
        "tests/test_brain_execution_coordinator.py",
        "app/services/brain/brain_execution_coordinator.py",
        "app/routes/security.py",
    ]),
    "Security monitoring and audit logging": ("TESTED", [
        "tests/test_security_audit_log.py",
        "app/services/security/security_audit_log_service.py",
        "app/routes/security.py",
    ]),
}


class PhaseZeroCapabilityService:
    """Expose the 99-capability inventory without overstating verification."""

    def inventory(self) -> list[dict[str, Any]]:
        entries = []
        for system_index, (system, capabilities) in enumerate(_SYSTEMS, start=1):
            for capability_index, name in enumerate(capabilities, start=1):
                evidence_status = _MILESTONE_EVIDENCE.get(name) or _MAIN_BRAIN_EVIDENCE.get(name)
                status = (
                    evidence_status[0]
                    if evidence_status
                    else "BLOCKED" if name in _BLOCKED
                    else "NOT_STARTED" if name in _NOT_STARTED
                    else "IN_PROGRESS"
                )
                evidence = list(evidence_status[1]) if evidence_status else []
                blocker = (
                    "Requires hardware, live provider, packaging, or OS-level acceptance."
                    if status == "BLOCKED"
                    else "Implementation and focused acceptance evidence remain incomplete."
                    if status == "IN_PROGRESS"
                    else "No implementation evidence recorded."
                    if status == "NOT_STARTED"
                    else None
                )
                entries.append({
                    "id": f"system-{system_index:02d}.capability-{capability_index:02d}",
                    "system": system,
                    "capability": name,
                    "status": status,
                    "evidence": evidence,
                    "blocker": blocker,
                })
        return entries

    def summary(self) -> dict[str, Any]:
        entries = self.inventory()
        counts = {status: sum(item["status"] == status for item in entries) for status in ("VERIFIED", "TESTED", "IMPLEMENTED", "IN_PROGRESS", "NOT_STARTED", "BLOCKED")}
        return {
            "success": True,
            "total": len(entries),
            "verified": counts["VERIFIED"],
            "counts": counts,
            "progress_percent": round(counts["VERIFIED"] / len(entries) * 100, 2),
            "systems": [
                {"system": system, "total": len(capabilities), "verified": sum(item["status"] == "VERIFIED" for item in entries if item["system"] == system)}
                for system, capabilities in _SYSTEMS
            ],
        }
