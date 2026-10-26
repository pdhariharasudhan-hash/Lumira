"""
mode_registry_service.py

Central registry for Lumira operating modes.

The registry defines available modes.

It does NOT:
- execute capabilities
- detect the active mode
- manage mode transitions
- modify BrainState
- create separate memory systems
- contain capability implementation logic

All modes share the same Lumira Core.

Ownership:
Handoff 13 - Milestone 13.1
"""

from typing import Dict, List, Optional

from app.services.modes.models.mode import (
    ModeDefinition,
)


class ModeRegistryService:
    """
    Central registry containing Lumira's operating modes.
    """

    def __init__(self) -> None:

        self._modes: Dict[
            str,
            ModeDefinition,
        ] = {}

        self._register_initial_modes()

    # ----------------------------------
    # Initial Modes
    # ----------------------------------

    def _register_initial_modes(self) -> None:
        """
        Register the eight primary Lumira modes.
        """

        modes = [

            ModeDefinition(
                id="personal",
                name="Personal Mode",
                description=(
                    "General personal assistance and life management."
                ),
                priority_capabilities=[
                    "personal_context",
                    "goals",
                    "tasks",
                    "planning",
                    "reminders",
                    "notes",
                    "calendar",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "personal",
                },
                activation_rules=[
                    "personal assistance",
                    "personal planning",
                    "daily organization",
                ],
            ),

            ModeDefinition(
                id="builder",
                name="Builder Mode",
                description=(
                    "Software, hardware, engineering, "
                    "prototype, and system creation."
                ),
                priority_capabilities=[
                    "project_engineering",
                    "code_generation",
                    "debugging",
                    "project_generation",
                    "artifact_manager",
                    "blueprint_generation",
                    "project_versioning",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "active_project",
                },
                activation_rules=[
                    "build",
                    "create project",
                    "develop",
                    "prototype",
                    "engineer",
                ],
            ),

            ModeDefinition(
                id="growth",
                name="Growth Mode",
                description=(
                    "Improving and growing projects, businesses, "
                    "products, and capabilities."
                ),
                priority_capabilities=[
                    "growth_strategy",
                    "market_analysis",
                    "product_improvement",
                    "revenue_analysis",
                    "user_growth",
                    "competitive_analysis",
                    "optimization",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "business_or_project_growth",
                },
                activation_rules=[
                    "grow",
                    "improve business",
                    "increase revenue",
                    "increase users",
                    "growth strategy",
                ],
            ),

            ModeDefinition(
                id="business",
                name="Business Mode",
                description="Planning and tracking business objectives, workflows, and evidence-led launch work.",
                priority_capabilities=[
                    "business_plan", "growth_strategy", "market_analysis",
                    "business_operations", "workflow_automation", "planning",
                    "goals", "search",
                ],
                restricted_capabilities=[],
                context_rules={"primary_context": "business_objective"},
                activation_rules=["business plan", "launch a business", "business idea"],
            ),

            ModeDefinition(
                id="creator",
                name="Creator Mode",
                description=(
                    "Creative production and content creation."
                ),
                priority_capabilities=[
                    "content_planning",
                    "presentations",
                    "posters",
                    "thumbnails",
                    "scripts",
                    "storyboards",
                    "ui_concepts",
                    "marketing_assets",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "creative_production",
                },
                activation_rules=[
                    "create content",
                    "write script",
                    "create presentation",
                    "marketing asset",
                    "creative project",
                ],
            ),

            ModeDefinition(
                id="generator",
                name="Generator Mode",
                description=(
                    "Generation of requested visual and design artifacts."
                ),
                priority_capabilities=[
                    "image_generation",
                    "blueprint_generation",
                    "schematic_generation",
                    "diagram_generation",
                    "architecture_diagrams",
                    "flowcharts",
                    "ui_design",
                    "product_concepts",
                    "industrial_design",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "artifact_generation",
                },
                activation_rules=[
                    "generate image",
                    "generate blueprint",
                    "generate schematic",
                    "generate diagram",
                    "generate design",
                ],
            ),

            ModeDefinition(
                id="research",
                name="Research Mode",
                description=(
                    "Investigating and understanding information."
                ),
                priority_capabilities=[
                    "web_research",
                    "document_research",
                    "knowledge_retrieval",
                    "technical_research",
                    "market_research",
                    "comparison",
                    "evidence_gathering",
                    "research_summaries",
                    "knowledge_extraction",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "research",
                },
                activation_rules=[
                    "research",
                    "investigate",
                    "analyze information",
                    "find sources",
                    "compare information",
                ],
            ),

            ModeDefinition(
                id="assistant",
                name="Assistant Mode",
                description=(
                    "General-purpose personal assistance and "
                    "immediate task support."
                ),
                priority_capabilities=[
                    "scheduling",
                    "reminders",
                    "calendar",
                    "tasks",
                    "email",
                    "daily_planning",
                    "notifications",
                    "voice",
                    "personal_organization",
                    "general_conversation",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "immediate_assistance",
                },
                activation_rules=[
                    "help me",
                    "assist me",
                    "schedule",
                    "remind me",
                    "organize",
                ],
            ),

            ModeDefinition(
                id="operations",
                name="Operations Mode",
                description=(
                    "Managing and automating ongoing systems "
                    "and operational processes."
                ),
                priority_capabilities=[
                    "business_operations",
                    "workflow_automation",
                    "scheduled_tasks",
                    "monitoring",
                    "notifications",
                    "process_optimization",
                    "file_automation",
                    "email_automation",
                    "system_monitoring",
                    "business_process_management",
                    "recurring_jobs",
                    "operational_dashboards",
                    "automated_reports",
                ],
                restricted_capabilities=[],
                context_rules={
                    "primary_context": "ongoing_operations",
                },
                activation_rules=[
                    "automate operations",
                    "monitor system",
                    "monitor business",
                    "run workflow",
                    "ongoing operations",
                    "operational automation",
                ],
            ),
        ]

        for mode in modes:
            self.register(mode)

    # ----------------------------------
    # Registration
    # ----------------------------------

    def register(
        self,
        mode: ModeDefinition,
    ) -> ModeDefinition:
        """
        Register a mode centrally.

        Existing modes are replaced by ID.
        """

        self._modes[mode.id] = mode

        return mode

    # ----------------------------------
    # Retrieval
    # ----------------------------------

    def get(
        self,
        mode_id: str,
    ) -> Optional[ModeDefinition]:
        """
        Return a mode by ID.

        Returns None when the mode does not exist.
        """

        return self._modes.get(
            mode_id
        )

    def require(
        self,
        mode_id: str,
    ) -> ModeDefinition:
        """
        Return a mode by ID or raise an error.
        """

        mode = self.get(
            mode_id
        )

        if mode is None:
            raise ValueError(
                f"Unknown Lumira mode: {mode_id}"
            )

        return mode

    def get_all(
        self,
    ) -> List[ModeDefinition]:
        """
        Return all registered modes.
        """

        return list(
            self._modes.values()
        )

    def get_ids(
        self,
    ) -> List[str]:
        """
        Return all registered mode IDs.
        """

        return list(
            self._modes.keys()
        )

    def exists(
        self,
        mode_id: str,
    ) -> bool:
        """
        Check whether a mode is registered.
        """

        return mode_id in self._modes

    def count(
        self,
    ) -> int:
        """
        Return the number of registered modes.
        """

        return len(
            self._modes
        )

    # ----------------------------------
    # Removal
    # ----------------------------------

    def unregister(
        self,
        mode_id: str,
    ) -> bool:
        """
        Remove a registered mode.

        Returns True when removed.
        """

        if mode_id not in self._modes:
            return False

        del self._modes[
            mode_id
        ]

        return True
