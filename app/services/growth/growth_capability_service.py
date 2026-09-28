"""
growth_capability_service.py

Deterministic Growth Mode capability implementation.

This service does not invent external market facts.
It converts a user request into a structured growth
execution framework.

Growth capabilities:
- growth_strategy
- market_analysis
- product_improvement
- revenue_analysis
- user_growth
- competitive_analysis
- optimization
"""

from typing import Any, Dict


class GrowthCapabilityService:
    """
    Deterministic execution service for Growth Mode.
    """

    def growth_strategy(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "growth_strategy",
            request,
            "growth strategy",
            [
                "define target customer",
                "define value proposition",
                "identify acquisition channels",
                "define conversion strategy",
                "define retention strategy",
                "define measurable growth metrics",
            ],
        )

    def business_plan(
        self,
        request: str,
        session_id: str | None = None,
        project_id: str | None = None,
        goal_id: str | None = None,
    ) -> Dict[str, Any]:
        """Create an evidence-led business plan and durable tracked tasks."""
        if not isinstance(request, str) or not request.strip() or len(request) > 10_000:
            return {"success": False, "status": "rejected", "code": "invalid_request", "message": "Business plan requests must contain 1 to 10000 characters."}

        tasks = [
            "Define the target customer and problem as hypotheses to validate.",
            "Specify the service offer, scope, exclusions, and delivery process.",
            "List equipment, skills, capacity, compliance, and startup-cost inputs to confirm.",
            "Set pricing assumptions and gather customer evidence before choosing prices.",
            "Plan customer interviews and a small demand-validation experiment.",
            "Create a launch checklist for delivery, support, invoicing, and risk handling.",
            "Choose success metrics using actual operating data once it is available.",
        ]
        from app.services.artifacts.artifact_manager_service import ArtifactManagerService
        from app.services.memory.memory_service import MemoryService
        from app.services.work_items.work_item_service import WorkItemService
        import json

        memory = MemoryService()
        try:
            goal = memory.update_goal(
                goal_id,
                title=request.strip()[:200],
                objective="Prepare an evidence-led business launch plan.",
                project_id=project_id,
                status="active",
            ) if goal_id else None
        except KeyError:
            goal = None
        if goal is None:
            goal = memory.create_goal(
                title=request.strip()[:200],
                objective="Prepare an evidence-led business launch plan.",
                priority="high",
                project_id=project_id,
            )
        workflow = WorkItemService().create_workflow(
            "business",
            f"Business plan: {request.strip()[:160]}",
            request.strip(),
            tasks,
            session_id=session_id,
            project_id=project_id,
            goal_id=goal["goal_id"],
        )
        memory.record_decision(
            decision="Use an evidence-led launch plan and validate assumptions before committing resources.",
            reason="Local business planning can structure work but has no verified market data source configured.",
            session_id=session_id,
            project_id=project_id,
            goal_id=goal["goal_id"],
            constraints=["Market size, demand, and pricing require external or user-provided evidence."],
            confidence=0.9,
        )
        plan = {
            "type": "business_launch_plan",
            "request": request.strip(),
            "goal_id": goal["goal_id"],
            "workflow_id": workflow["workflow_id"],
            "tasks": workflow["tasks"],
            "assumptions": ["Customer need and willingness to pay are unverified hypotheses."],
            "evidence_needed": ["Customer interviews", "Observed demand", "Actual cost and capacity data"],
            "metrics": {"data_available": False, "values": {}},
            "status": "planned",
        }
        try:
            artifact = ArtifactManagerService().create_artifact(
                "exports", json.dumps(plan, ensure_ascii=False), "business_plan", "json"
            )
            memory.update_goal(goal["goal_id"], artifact_ids=[artifact["artifact_id"]])
        except Exception:
            return {
                "success": False,
                "status": "failed",
                "code": "artifact_storage_failed",
                "message": "The plan and tasks were recorded, but the business-plan artifact could not be stored.",
                "goal_id": goal["goal_id"],
                "workflow_id": workflow["workflow_id"],
            }
        return {
            "success": True,
            "status": "accept",
            "capability": "business_plan",
            "plan": plan,
            "goal": goal,
            "workflow": workflow,
            "artifact": artifact,
        }

    def market_analysis(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "market_analysis",
            request,
            "market analysis",
            [
                "define target market",
                "segment potential customers",
                "identify customer problems",
                "identify existing alternatives",
                "compare positioning",
                "identify evidence required",
                "define market validation tests",
            ],
        )

    def product_improvement(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "product_improvement",
            request,
            "product improvement",
            [
                "identify current product objective",
                "identify user pain points",
                "prioritize improvement opportunities",
                "define proposed changes",
                "define validation criteria",
                "test improvements",
                "measure resulting impact",
            ],
        )

    def revenue_analysis(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "revenue_analysis",
            request,
            "revenue analysis",
            [
                "identify revenue sources",
                "identify pricing model",
                "identify conversion points",
                "identify revenue leakage",
                "compare revenue opportunities",
                "define measurable revenue metrics",
                "validate proposed changes",
            ],
        )

    def user_growth(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "user_growth",
            request,
            "user growth",
            [
                "define target users",
                "define acquisition channels",
                "create acquisition experiments",
                "define activation event",
                "define retention strategy",
                "measure conversion funnel",
                "repeat validated growth experiments",
            ],
        )

    def competitive_analysis(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "competitive_analysis",
            request,
            "competitive analysis",
            [
                "identify relevant competitors",
                "identify competitor offerings",
                "compare target customers",
                "compare value propositions",
                "compare pricing models",
                "identify differentiation opportunities",
                "validate competitive assumptions",
            ],
        )

    def optimize(
        self,
        request: str,
    ) -> Dict[str, Any]:

        return self._result(
            "optimization",
            request,
            "optimization",
            [
                "identify target process",
                "measure current baseline",
                "identify bottlenecks",
                "identify highest-impact changes",
                "apply smallest useful improvement",
                "measure resulting change",
                "repeat using measured results",
            ],
        )

    @staticmethod
    def _result(
        capability: str,
        request: str,
        objective: str,
        steps: list[str],
    ) -> Dict[str, Any]:

        normalized = (
            request.strip()
            if isinstance(request, str)
            else ""
        )

        return {
            "success": True,
            "capability": capability,
            "request": normalized,
            "objective": objective,
            "steps": list(steps),
            "status": "accept",
        }
