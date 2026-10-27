import json
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.projects.project_discovery_service import ProjectDiscoveryService
from app.services.projects.project_writer import ProjectWriter
from app.services.validation.code_validation_service import CodeValidationService
from app.services.features.feature_activation_service import (
    FeatureActivationService
)

from app.services.image.image_generation_service import (
    ImageGenerationService
)

from app.services.search.unified_search_service import (
    UnifiedSearchService
)

from app.services.capabilities.mode_capability_service import (
    ModeCapabilityService
)

from app.services.modes.models.mode_state import (
    ModeState
)



from app.services.builder.builder_service import (
    BuilderService
)

from app.services.execution.execute_service import (
    ExecuteService
)

from app.services.code.code_service import (
    CodeService
)


from app.services.planner.planner_service import (
    PlannerService
)
from app.services.planner.plan_executor_v3 import PlanExecutorV3

from app.services.growth.growth_capability_service import (
    GrowthCapabilityService
)





from app.services.research.research_capability_service import (
    ResearchCapabilityService
)

from app.services.operations.operations_capability_service import (
    OperationsCapabilityService
)

from app.services.creator.creator_capability_service import (
    CreatorCapabilityService
)

from app.services.generator.generator_capability_service import (
    GeneratorCapabilityService
)

from app.services.assistant.assistant_capability_service import (
    AssistantCapabilityService
)

from app.services.personal.personal_capability_service import (
    PersonalCapabilityService
)


class CapabilityRouterService:

    def __init__(self):

        self.features = (
            FeatureActivationService()
        )

        self.images = (
            ImageGenerationService()
        )

        self.search = (
            UnifiedSearchService()
        )

        self.builder = (
            BuilderService()
        )

        self.executor = (
            ExecuteService()
        )

        self.code = (
            CodeService()
        )


        self.mode_capabilities = (
            ModeCapabilityService()
        )

        self.planner = (
            PlannerService()
        )


        self.research = (
            ResearchCapabilityService()
        )

        self.operations = (
            OperationsCapabilityService()
        )

        self.creator = (
            CreatorCapabilityService()
        )

        self.generator = (
            GeneratorCapabilityService()
        )

        self.assistant = (
            AssistantCapabilityService()
        )

        self.personal = (
            PersonalCapabilityService()
        )


        self.growth = (
            GrowthCapabilityService()
        )
        self.code_validator = CodeValidationService()
        self.project_writer = ProjectWriter()
        self.project_discovery = ProjectDiscoveryService()
        self.artifact_manager = ArtifactManagerService()

    # ==========================
    # MAIN ROUTER
    # ==========================

    @staticmethod
    def _with_mode(
        result,
        mode_state=None,
    ):
        if not isinstance(result, dict):
            result = {
                "success": True,
                "result": result,
            }

        output = dict(result)

        if mode_state is not None:
            output["mode"] = mode_state.active_mode

        return output



    def execute(
        self,
        capability: str,
        payload: dict = None,
        mode_state: ModeState = None,
    ):

        payload = payload or {}

        if not isinstance(payload, dict):
            return {"success": False, "status": "reject", "error": {"code": "validation_error", "message": "Capability payload must be an object."}}
        for input_key in ("idea", "request", "command", "query"):
            value = payload.get(input_key)
            if value is not None and (not isinstance(value, str) or len(value) > 10000):
                return {"success": False, "status": "reject", "error": {"code": "validation_error", "message": f"{input_key} must be a string no longer than 10000 characters."}}

        if mode_state is not None:
            resolution = (
                self.mode_capabilities.resolve(
                    mode_state,
                    capability,
                )
            )

            if not resolution["allowed"]:
                return {
                    "success": False,
                    "message": (
                        "Capability restricted by active mode: "
                        + resolution["mode"]
                    ),
                    "mode": resolution["mode"],
                    "capability": resolution["capability"],
                    "restricted": True,
                    "priority": resolution["priority"],
                }

        capability = (
            capability
            .strip()
            .lower()
        )
        if "request" not in payload and isinstance(payload.get("content"), str):
            payload["request"] = payload["content"]

        # --------------------------
        # FEATURE ACTIVATION
        # --------------------------

        # --------------------------
        # PLANNING
        # --------------------------

        if capability == "planning":

            goal = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            result = self.planner.create_plan(
                goal
            )

            return self._with_mode(
                result,
                mode_state
            )

        # Bounded end-to-end planning and code generation; generated code is not run.
        if capability == "project_pipeline":
            goal = payload.get(
                "goal",
                payload.get("request", payload.get("idea", payload.get("command", ""))),
            )
            return self._with_mode(PlanExecutorV3().execute(goal), mode_state)

        if capability == "activate_feature":

            return self.features.activate(

                payload.get(
                    "feature"
                )
            )

        if capability == "deactivate_feature":

            return self.features.deactivate(

                payload.get(
                    "feature"
                )
            )

        if capability == "feature_status":

            return self.features.status(

                payload.get(
                    "feature"
                )
            )

        if capability == "list_features":

            return self.features.list_features()

        # --------------------------
        # GROWTH
        # --------------------------

        if capability == "growth_strategy":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.growth_strategy(
                    request
                ),
                mode_state
            )

        if capability == "business_plan":
            request = payload.get("request", payload.get("idea", payload.get("command", "")))
            result = self.growth.business_plan(
                request,
                session_id=payload.get("session_id"),
                project_id=payload.get("project_id"),
                goal_id=payload.get("goal_id"),
            )
            return self._with_mode(result, mode_state)

        if capability == "market_analysis":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.market_analysis(
                    request
                ),
                mode_state
            )

        if capability == "product_improvement":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.product_improvement(
                    request
                ),
                mode_state
            )

        if capability == "revenue_analysis":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.revenue_analysis(
                    request
                ),
                mode_state
            )

        if capability == "user_growth":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.user_growth(
                    request
                ),
                mode_state
            )

        if capability == "competitive_analysis":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.competitive_analysis(
                    request
                ),
                mode_state
            )

        if capability == "optimization":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.growth.optimize(
                    request
                ),
                mode_state
            )

        # --------------------------
        # BUILDER / PROJECT ENGINEERING
        # --------------------------

        if capability == "project_engineering":

            idea = payload.get(
                "idea",
                payload.get(
                    "request",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.builder.build(
                    idea
                ),
                mode_state
            )

        if capability == "code_generation":

            idea = payload.get(
                "idea",
                payload.get(
                    "request",
                    ""
                )
            )

            builder_result = (
                self.builder.build(
                    idea
                )
            )

            if builder_result.get("status") != "accept":

                return self._with_mode(
                    {
                        "success": False,
                        "status": builder_result.get(
                            "status",
                            "reject"
                        ),
                        "builder": builder_result,
                    },
                    mode_state
                )

            execution_result = (
                self.executor.execute(
                    idea,
                    builder_result
                )
            )

            if execution_result.get("status") != "accept":

                return self._with_mode(
                    {
                        "success": False,
                        "status": execution_result.get(
                            "status",
                            "reject"
                        ),
                        "builder": builder_result,
                        "execution": execution_result,
                    },
                    mode_state
                )

            code_result = (
                self.code.generate(
                    idea,
                    execution_result
                )
            )

            return self._with_mode(
                {
                    "success": True,
                    "status": code_result.get(
                        "status",
                        "accept"
                    ),
                    "builder": builder_result,
                    "execution": execution_result,
                    "code": code_result,
                },
                mode_state
            )


        # --------------------------
        # IMAGE GENERATION
        # --------------------------

        if capability == "generate_image":

            return self.images.generate(

                prompt=
                payload.get(
                    "prompt",
                    ""
                ),

                image_type=
                payload.get(
                    "image_type",
                    "image"
                )
            )

        # --------------------------
        # SEARCH
        # --------------------------

        if capability == "search":

            return self._with_mode(


                self.search.search_all(


                    payload.get(


                        "query",


                        ""


                    )


                ),


                mode_state


            )


        # --------------------------
        # RESEARCH
        # --------------------------

        if capability == "web_research":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.web_research(
                    request
                ),
                mode_state
            )

        if capability == "document_research":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.document_research(
                    request
                ),
                mode_state
            )

        if capability == "knowledge_retrieval":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.knowledge_retrieval(
                    request
                ),
                mode_state
            )

        if capability == "technical_research":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.technical_research(
                    request
                ),
                mode_state
            )

        if capability == "market_research":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.market_research(
                    request
                ),
                mode_state
            )

        if capability == "comparison":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.comparison(
                    request
                ),
                mode_state
            )

        if capability == "evidence_gathering":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.evidence_gathering(
                    request
                ),
                mode_state
            )

        if capability == "research_summaries":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.research_summaries(
                    request
                ),
                mode_state
            )

        if capability == "knowledge_extraction":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.research.knowledge_extraction(
                    request
                ),
                mode_state
            )


        # --------------------------
        # OPERATIONS
        # --------------------------

        if capability == "business_operations":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.business_operations(
                    request,
                    session_id=payload.get("session_id"),
                    project_id=payload.get("project_id"),
                    goal_id=payload.get("goal_id"),
                ),
                mode_state
            )

        if capability == "workflow_automation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.workflow_automation(
                    request,
                    session_id=payload.get("session_id"),
                    project_id=payload.get("project_id"),
                    goal_id=payload.get("goal_id"),
                ),
                mode_state
            )

        if capability == "scheduled_tasks":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.scheduled_tasks(
                    request
                ),
                mode_state
            )

        if capability == "monitoring":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.monitoring(
                    request
                ),
                mode_state
            )

        if capability == "process_optimization":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.process_optimization(
                    request
                ),
                mode_state
            )

        if capability == "file_automation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.file_automation(
                    request
                ),
                mode_state
            )

        if capability == "email_automation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.email_automation(
                    request
                ),
                mode_state
            )

        if capability == "system_monitoring":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.system_monitoring(
                    request
                ),
                mode_state
            )

        if capability == "business_process_management":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.business_process_management(
                    request
                ),
                mode_state
            )

        if capability == "recurring_jobs":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.recurring_jobs(
                    request
                ),
                mode_state
            )

        if capability == "operational_dashboards":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.operational_dashboards(
                    request
                ),
                mode_state
            )

        if capability == "automated_reports":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.operations.automated_reports(
                    request
                ),
                mode_state
            )


        # --------------------------
        # CREATOR
        # --------------------------

        if capability == "content_planning":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.content_planning(
                    request
                ),
                mode_state
            )

        if capability == "presentations":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.presentations(
                    request
                ),
                mode_state
            )

        if capability == "posters":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.posters(
                    request
                ),
                mode_state
            )

        if capability == "thumbnails":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.thumbnails(
                    request
                ),
                mode_state
            )

        if capability == "scripts":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.scripts(
                    request
                ),
                mode_state
            )

        if capability == "storyboards":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.storyboards(
                    request
                ),
                mode_state
            )

        if capability == "ui_concepts":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.ui_concepts(
                    request
                ),
                mode_state
            )

        if capability == "marketing_assets":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.creator.marketing_assets(
                    request
                ),
                mode_state
            )


        # --------------------------
        # GENERATOR
        # --------------------------

        if capability == "image_generation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.image_generation(
                    request
                ),
                mode_state
            )

        if capability == "document_generation":
            request = payload.get("request", payload.get("idea", payload.get("command", "")))
            return self._with_mode(self.generator.document_generation(request), mode_state)

        if capability == "video_generation":
            request = payload.get("request", payload.get("idea", payload.get("command", "")))
            return self._with_mode(self.generator.video_generation(request), mode_state)

        if capability == "schematic_generation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.schematic_generation(
                    request
                ),
                mode_state
            )

        if capability == "diagram_generation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.diagram_generation(
                    request
                ),
                mode_state
            )

        if capability == "architecture_diagrams":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.architecture_diagrams(
                    request
                ),
                mode_state
            )

        if capability == "flowcharts":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.flowcharts(
                    request
                ),
                mode_state
            )

        if capability == "ui_design":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.ui_design(
                    request
                ),
                mode_state
            )

        if capability == "product_concepts":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.product_concepts(
                    request
                ),
                mode_state
            )

        if capability == "industrial_design":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.generator.industrial_design(
                    request
                ),
                mode_state
            )


        # --------------------------
        # ASSISTANT
        # --------------------------

        if capability == "scheduling":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.scheduling(
                    request
                ),
                mode_state
            )

        if capability == "email":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.email(
                    request
                ),
                mode_state
            )

        if capability == "daily_planning":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.daily_planning(
                    request
                ),
                mode_state
            )

        if capability == "notifications":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.notifications(
                    request
                ),
                mode_state
            )

        if capability == "voice":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.voice(
                    request
                ),
                mode_state
            )

        if capability == "personal_organization":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.personal_organization(
                    request
                ),
                mode_state
            )

        if capability == "general_conversation":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.assistant.general_conversation(
                    request
                ),
                mode_state
            )


        # --------------------------
        # PERSONAL
        # --------------------------

        if capability == "personal_context":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.personal_context(
                    request
                ),
                mode_state
            )

        if capability == "goals":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.goals(
                    request
                ),
                mode_state
            )

        if capability == "tasks":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.tasks(
                    request
                ),
                mode_state
            )

        if capability == "reminders":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.reminders(
                    request
                ),
                mode_state
            )

        if capability == "notes":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.notes(
                    request
                ),
                mode_state
            )

        if capability == "calendar":

            request = payload.get(
                "request",
                payload.get(
                    "idea",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            return self._with_mode(
                self.personal.calendar(
                    request
                ),
                mode_state
            )


        # --------------------------
        # UNKNOWN
        # --------------------------

        # ==========================
        # REAL BUILDER CAPABILITIES
        # ==========================

        if capability == "debugging":

            idea = payload.get(
                "idea",
                payload.get(
                    "request",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            builder_result = self.builder.build(idea)

            if builder_result.get("status") != "accept":
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "debugging",
                        "status": builder_result.get(
                            "status",
                            "reject"
                        ),
                        "builder": builder_result,
                    },
                    mode_state,
                )

            execution_result = self.executor.execute(
                idea,
                builder_result,
            )

            if execution_result.get("status") != "accept":
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "debugging",
                        "status": execution_result.get(
                            "status",
                            "reject"
                        ),
                        "builder": builder_result,
                        "execution": execution_result,
                    },
                    mode_state,
                )

            code_result = self.code.generate(
                idea,
                execution_result,
            )

            files = {}

            if isinstance(code_result, dict):
                files = code_result.get(
                    "files",
                    {}
                )

            validation_result = (
                self.code_validator.validate(files)
            )

            validation_ok = isinstance(validation_result, dict) and validation_result.get("valid") is True

            return self._with_mode(
                {
                    "success": validation_ok,
                    "capability": "debugging",
                    "status": "accept" if validation_ok else "reject",
                    "builder": builder_result,
                    "execution": execution_result,
                    "code": code_result,
                    "validation": validation_result,
                },
                mode_state,
            )

        if capability == "project_generation":

            idea = payload.get(
                "idea",
                payload.get(
                    "request",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            if not isinstance(idea, str):
                idea = str(idea)

            idea = idea.strip()

            if not idea:
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": "reject",
                        "error": "idea is required",
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 1. BUILD
            # ------------------------------------------------

            builder_result = self.builder.build(
                idea
            )

            if builder_result.get("status") != "accept":
                return self._with_mode(
                    {"success": False, "status": builder_result.get("status", "refine"), "builder": builder_result},
                    mode_state,
                )

            # ------------------------------------------------
            # 2. EXECUTE / PLAN IMPLEMENTATION
            # ------------------------------------------------

            execution_result = self.executor.execute(
                idea,
                builder_result,
            )

            execution_status = "accept"

            if isinstance(
                execution_result,
                dict,
            ):
                execution_status = (
                    execution_result.get(
                        "status",
                        "accept",
                    )
                )

            if execution_status != "accept":
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": execution_status,
                        "builder": builder_result,
                        "execution": execution_result,
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 3. GENERATE CODE
            # ------------------------------------------------

            code_result = self.code.generate(
                idea,
                execution_result,
            )

            if not isinstance(
                code_result,
                dict,
            ):
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": "reject",
                        "error": "code generation returned invalid result",
                        "builder": builder_result,
                        "execution": execution_result,
                    },
                    mode_state,
                )

            files = code_result.get(
                "files",
                {},
            )

            if not isinstance(files, dict) or not files:
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": "reject",
                        "error": "code generation produced no files",
                        "builder": builder_result,
                        "execution": execution_result,
                        "code": code_result,
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 4. VALIDATE GENERATED CODE
            # ------------------------------------------------

            validation_result = self.code_validator.validate(
                files
            )

            validation_ok = False

            if isinstance(
                validation_result,
                dict,
            ):
                validation_ok = (
                    validation_result.get(
                        "valid",
                        validation_result.get(
                            "success",
                            False,
                        ),
                    )
                    is True
                )

            if not validation_ok:
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": "reject",
                        "error": "generated project failed validation",
                        "builder": builder_result,
                        "execution": execution_result,
                        "code": code_result,
                        "validation": validation_result,
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 5. RESOLVE PROJECT NAME
            # ------------------------------------------------

            project_name = payload.get(
                "project_name"
            )

            if not project_name:
                project_name = code_result.get(
                    "code_target"
                )

            if not project_name:
                project_name = (
                    builder_result.get(
                        "entity"
                    )
                    if isinstance(
                        builder_result,
                        dict,
                    )
                    else None
                )

            if not project_name:
                project_name = "lumira_project"

            project_name = str(
                project_name
            ).strip()

            # ------------------------------------------------
            # 6. BUILD METADATA
            # ------------------------------------------------

            metadata = {
                "project": project_name,
                "idea": idea,
                "capability": "project_generation",
                "code_target": code_result.get(
                    "code_target"
                ),
                "file_plan": code_result.get(
                    "file_plan",
                    [],
                ),
                "implementation_steps": code_result.get(
                    "implementation_steps",
                    [],
                ),
                "test_steps": code_result.get(
                    "test_steps",
                    [],
                ),
                "builder": builder_result,
                "execution": execution_result,
                "validation": validation_result,
            }

            # ------------------------------------------------
            # 7. PERSIST PROJECT + VERSION
            # ------------------------------------------------

            try:
                saved_path = self.project_writer.save(
                    project_name,
                    files,
                    metadata,
                )
            except (OSError, ValueError) as error:
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": "reject",
                        "error": {"code": "project_save_failed", "message": str(error)},
                        "builder": builder_result,
                        "execution": execution_result,
                        "code": code_result,
                        "validation": validation_result,
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 8. RETURN COMPLETE RESULT
            # ------------------------------------------------

            return self._with_mode(
                {
                    "success": True,
                    "capability": "project_generation",
                    "status": "accept",
                    "project_name": project_name,
                    "saved_path": saved_path,
                    "builder": builder_result,
                    "execution": execution_result,
                    "code": code_result,
                    "validation": validation_result,
                    "files": list(files.keys()),
                    "metadata": metadata,
                },
                mode_state,
            )

        # ==========================
        # ARTIFACT MANAGEMENT
        # ==========================

        if capability == "artifact_manager":

            action = str(
                payload.get(
                    "action",
                    "list"
                )
            ).strip().lower()

            if action == "create":

                result = self.artifact_manager.create_artifact(
                    artifact_type=payload.get(
                        "artifact_type",
                        "txt"
                    ),
                    content=payload.get(
                        "content",
                        ""
                    ),
                    source=payload.get(
                        "source",
                        "lumira"
                    ),
                    extension=payload.get(
                        "extension",
                        "txt"
                    ),
                )

                return self._with_mode(
                    {
                        "success": True,
                        "capability": "artifact_manager",
                        "action": "create",
                        "status": "accept",
                        "result": result,
                    },
                    mode_state,
                )

            if action == "get":

                artifact_id = payload.get(
                    "artifact_id"
                )

                if not artifact_id:
                    return self._with_mode(
                        {
                            "success": False,
                            "capability": "artifact_manager",
                            "error": "artifact_id is required",
                        },
                        mode_state,
                    )

                result = self.artifact_manager.get_artifact(
                    artifact_id
                )

                return self._with_mode(
                    {
                        "success": result is not None,
                        "capability": "artifact_manager",
                        "action": "get",
                        "status": "accept",
                        "result": result,
                    },
                    mode_state,
                )

            if action == "search":

                result = self.artifact_manager.search(
                    artifact_type=payload.get(
                        "artifact_type"
                    )
                )

                return self._with_mode(
                    {
                        "success": True,
                        "capability": "artifact_manager",
                        "action": "search",
                        "status": "accept",
                        "result": result,
                    },
                    mode_state,
                )

            if action == "list":

                result = self.artifact_manager.get_all_artifacts()

                return self._with_mode(
                    {
                        "success": True,
                        "capability": "artifact_manager",
                        "action": "list",
                        "status": "accept",
                        "result": result,
                    },
                    mode_state,
                )

            return self._with_mode(
                {
                    "success": False,
                    "capability": "artifact_manager",
                    "error": (
                        f"unsupported action: {action}"
                    ),
                },
                mode_state,
            )

        # ==========================
        # BLUEPRINT
        # ==========================

        if capability == "blueprint_generation":

            idea = payload.get(
                "idea",
                payload.get(
                    "request",
                    payload.get(
                        "command",
                        ""
                    )
                )
            )

            if not isinstance(idea, str):
                idea = str(idea)

            idea = idea.strip()

            if not idea:
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "blueprint_generation",
                        "status": "reject",
                        "error": "idea is required",
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 1. BUILD ENGINEERING PLAN
            # ------------------------------------------------

            builder_result = self.builder.build(
                idea
            )

            if builder_result.get("status") != "accept":
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_generation",
                        "status": builder_result.get("status", "refine"),
                        "builder": builder_result,
                    },
                    mode_state,
                )

            if not isinstance(
                builder_result,
                dict,
            ):
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "blueprint_generation",
                        "status": "reject",
                        "error": "builder returned invalid result",
                    },
                    mode_state,
                )

            builder_status = builder_result.get(
                "status",
                "accept",
            )

            if builder_status != "accept":
                return self._with_mode(
                    {
                        "success": False,
                        "capability": "blueprint_generation",
                        "status": builder_status,
                        "builder": builder_result,
                    },
                    mode_state,
                )

            # ------------------------------------------------
            # 2. BUILD DETERMINISTIC BLUEPRINT
            # ------------------------------------------------

            steps = builder_result.get(
                "suggested_steps",
                [],
            )

            blueprint = {
                "type": "blueprint",
                "version": "1.0",
                "idea": idea,
                "objective": builder_result.get(
                    "objective",
                    "",
                ),
                "scope": builder_result.get(
                    "scope",
                    "",
                ),
                "priority": builder_result.get(
                    "priority",
                    "",
                ),
                "status": "generated",
                "steps": steps,
                "step_count": len(steps),
            }

            # ------------------------------------------------
            # 3. SERIALIZE BLUEPRINT
            # ------------------------------------------------

            blueprint_text = json.dumps(
                blueprint,
                indent=4,
                ensure_ascii=False,
            )

            # ------------------------------------------------
            # 4. PERSIST BLUEPRINT ARTIFACT
            # ------------------------------------------------

            artifact = (
                self.artifact_manager.create_artifact(
                    artifact_type="blueprints",
                    content=blueprint_text,
                    source="blueprint_generation",
                    extension="json",
                )
            )

            # ------------------------------------------------
            # 5. RETURN COMPLETE RESULT
            # ------------------------------------------------

            return self._with_mode(
                {
                    "success": True,
                    "capability": "blueprint_generation",
                    "status": "accept",
                    "idea": idea,
                    "blueprint": blueprint,
                    "artifact": artifact,
                },
                mode_state,
            )

        # ==========================
        # PROJECT VERSIONING
        # ==========================

        if capability == "project_versioning":

            action = str(
                payload.get(
                    "action",
                    "list"
                )
            ).strip().lower()

            project_name = payload.get(
                "project_name"
            )

            if action == "list":

                result = self.project_discovery.get_projects()

            elif action == "project":

                if not project_name:
                    return self._with_mode(
                        {
                            "success": False,
                            "capability": "project_versioning",
                            "error": "project_name is required",
                        },
                        mode_state,
                    )

                result = self.project_discovery.get_project(
                    project_name
                )

            elif action == "metadata":

                if not project_name:
                    return self._with_mode(
                        {
                            "success": False,
                            "capability": "project_versioning",
                            "error": "project_name is required",
                        },
                        mode_state,
                    )

                result = self.project_discovery.get_metadata(
                    project_name
                )

            elif action == "versions":

                if not project_name:
                    return self._with_mode(
                        {
                            "success": False,
                            "capability": "project_versioning",
                            "error": "project_name is required",
                        },
                        mode_state,
                    )

                result = self.project_discovery.get_versions(
                    project_name
                )

            else:

                return self._with_mode(
                    {
                        "success": False,
                        "capability": "project_versioning",
                        "error": (
                            f"unsupported action: {action}"
                        ),
                    },
                    mode_state,
                )

            return self._with_mode(
                {
                    "success": True,
                    "capability": "project_versioning",
                    "action": action,
                    "project_name": project_name,
                    "status": "accept",
                    "result": result,
                },
                mode_state,
            )
        return {

            "success":
            False,

            "message":
            f"Unknown capability: {capability}"
        }
