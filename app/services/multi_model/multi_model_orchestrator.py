from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from app.services.multi_model.model_registry import MultiModelRegistry
from app.services.multi_model.model_health_service import ModelHealthService
from app.services.providers.provider_access_policy_service import (
    ProviderAccessDenied,
    ProviderAccessPolicyService,
)
from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.sessions.session_manager_service import (
    redact_sensitive_text,
    redact_sensitive_value,
)


@dataclass(frozen=True)
class OrchestrationPolicy:
    mode: str
    max_models: int
    parallel: bool


class MultiModelIntelligenceOrchestrator:
    """RAM-aware multi-model orchestration with explicit provider policy checks."""

    MODES = {
        "fast": OrchestrationPolicy("fast", 1, False),
        "smart": OrchestrationPolicy("smart", 2, True),
        "compare": OrchestrationPolicy("compare", 4, True),
        "maximum_quality": OrchestrationPolicy("maximum_quality", 8, True),
        "offline": OrchestrationPolicy("offline", 4, True),
    }
    TASK_TYPES = {"reply", "coding", "research", "planning"}
    MAX_PROMPT = 20_000
    MAX_MODEL_OUTPUT = 20_000
    MAX_CONTEXT_KEYS = 50
    MAX_CONTEXT_BYTES = 64_000
    TOOL_CATALOG = (
        (
            "research",
            (
                "research", "compare", "comparison", "versus", "vs", "investigate",
                "analyze", "analyse", "analysis", "evidence", "summarize", "summarise",
                "extract knowledge", "market research", "technical research",
                "document research", "knowledge retrieval", "find sources",
                "gather sources", "fact check", "fact-check",
            ),
            "research_agent",
        ),
        (
            "planning",
            (
                "plan", "planning", "steps", "roadmap", "prioritize", "prioritise",
                "break down", "decompose", "milestone", "schedule", "sequence tasks", "goal",
            ),
            "planner_agent",
        ),
        (
            "coding",
            (
                "debug", "fix", "repair", "refactor", "implement", "code", "api", "app",
                "website", "software", "program", "script", "compile", "syntax error",
                "bug", "patch", "generate files",
            ),
            "code_agent",
        ),
    )

    def __init__(self, *, provider_policy=None, resource_budget=None, model_health=None):
        self.provider_policy = provider_policy or ProviderAccessPolicyService()
        self.resource_budget = resource_budget or ResourceBudgetService()
        self.model_health = model_health or ModelHealthService()

    @staticmethod
    def _matches_tool_keyword(normalized: str, keyword: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", normalized) is not None

    @classmethod
    def select_tool(cls, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip() or len(task.strip()) > cls.MAX_PROMPT:
            return {"success": False, "code": "invalid_task", "selected_tool": None}
        normalized = " ".join(task.casefold().split())
        for tool, keywords, agent in cls.TOOL_CATALOG:
            if any(cls._matches_tool_keyword(normalized, keyword) for keyword in keywords):
                return {
                    "success": True,
                    "selected_tool": tool,
                    "agent": agent,
                    "reason": "deterministic_task_capability_match",
                    "available_tools": [item[0] for item in cls.TOOL_CATALOG],
                }
        return {
            "success": False,
            "code": "no_matching_tool",
            "selected_tool": None,
            "available_tools": [item[0] for item in cls.TOOL_CATALOG],
        }

    def available_models(self):
        return [
            {
                "model_id": profile.model_id,
                "provider": profile.provider,
                "capabilities": sorted(profile.capabilities),
                "enabled": profile.enabled,
                "priority": profile.priority,
                "health": self.model_health.can_attempt(profile.model_id),
            }
            for profile in MultiModelRegistry.list()
        ]

    def _resource_policy(self) -> dict[str, Any]:
        try:
            guidance = self.resource_budget.execution_guidance()
            if not isinstance(guidance, dict):
                raise ValueError("resource guidance is invalid")
            pressure = guidance.get("resource_pressure", "unknown")
            profile = guidance.get("resource_profile", "low_memory")
            max_local = guidance.get("max_concurrent_local_model_requests", 1)
            if isinstance(max_local, bool) or not isinstance(max_local, int) or max_local < 1:
                max_local = 1
            constrained = profile == "low_memory" or pressure in {"critical", "constrained", "unknown"}
            max_models = 2 if constrained else 4
            return {
                "profile": profile,
                "pressure": pressure,
                "max_models": max_models,
                "max_local_models": 1 if constrained else 2,
                "max_external_models": 1 if constrained else 2,
                "max_local_concurrency": min(max_local, 1 if constrained else 2),
                "parallel_external": not constrained,
            }
        except Exception:
            # Unknown resource state is treated conservatively on small hosts.
            return {
                "profile": "conservative_fallback",
                "pressure": "unknown",
                "max_models": 2,
                "max_local_models": 1,
                "max_external_models": 1,
                "max_local_concurrency": 1,
                "parallel_external": False,
            }

    def run(
        self,
        *,
        prompt: str,
        task_type: str = "reply",
        mode: str = "smart",
        context: dict[str, Any] | None = None,
    ):
        prompt = self._prompt(prompt)
        if not isinstance(task_type, str) or task_type not in self.TASK_TYPES:
            raise ValueError("unsupported task_type")
        if not isinstance(mode, str) or mode not in self.MODES:
            raise ValueError("unsupported orchestration mode")
        context = self._context({} if context is None else context)
        policy = self.MODES[mode]
        resource = self._resource_policy()
        selected = MultiModelRegistry.eligible(task_type)
        if mode == "offline":
            selected = [
                (profile, worker)
                for profile, worker in selected
                if profile.provider.casefold() in {"local", "ollama", "offline"}
            ]
        selected_limit = min(policy.max_models, resource["max_models"])
        bounded_selected = []
        scope_counts = {"local": 0, "external": 0}
        for profile, worker in selected:
            scope = self.provider_policy.provider_scope(worker)
            scope_limit = resource["max_local_models"] if scope == "local" else resource["max_external_models"]
            if scope_counts[scope] >= scope_limit:
                continue
            bounded_selected.append((profile, worker))
            scope_counts[scope] += 1
            if len(bounded_selected) >= selected_limit:
                break
        selected = bounded_selected
        health_blocked = []
        available = []
        for profile, worker in selected:
            health = self.model_health.can_attempt(profile.model_id)
            if health.get("allowed") is True:
                available.append((profile, worker))
            else:
                health_blocked.append({"model_id": profile.model_id, "code": health.get("code", "model_health_unavailable")})
        selected = available
        if not selected and health_blocked:
            return {
                "success": False,
                "code": "models_temporarily_unavailable",
                "mode": mode,
                "task_type": task_type,
                "resource_policy": resource,
                "blocked_models": health_blocked,
                "message": "All eligible models are currently unavailable or have an open failure circuit.",
                "candidates": [],
            }
        if not selected:
            return {
                "success": False,
                "code": "no_model_available",
                "mode": mode,
                "task_type": task_type,
                "resource_policy": resource,
                "message": "No eligible configured model is available for this request.",
                "candidates": [],
            }

        local_selected = [
            (profile, worker)
            for profile, worker in selected
            if self.provider_policy.provider_scope(worker) == "local"
        ]
        parallel = policy.parallel and resource["parallel_external"] and not local_selected
        if local_selected and resource["max_local_concurrency"] <= 1:
            parallel = False

        results = self._collect(selected, prompt, context, task_type, parallel)
        valid = [
            item for item in results
            if item.get("success") is True
            and isinstance(item.get("content"), str)
            and item["content"].strip()
        ]
        if not valid:
            return {
                "success": False,
                "code": "all_models_failed",
                "mode": mode,
                "task_type": task_type,
                "resource_policy": resource,
                "message": "Configured models did not return a usable policy-authorized response.",
                "candidates": results,
            }
        scored = [self._score(item, prompt, task_type) for item in valid]
        scored.sort(key=lambda item: (-item["score"], item["model_id"]))
        winner = scored[0]
        return {
            "success": True,
            "mode": mode,
            "task_type": task_type,
            "response": winner["content"],
            "selected_model": winner["model_id"],
            "resource_policy": resource,
            "selection": {
                "score": winner["score"],
                "reason": winner["reason"],
                "candidate_count": len(results),
                "usable_candidate_count": len(valid),
            },
            "candidates": scored,
        }

    def _collect(self, selected, prompt, context, task_type, parallel):
        def invoke(profile, worker):
            import time
            started = time.monotonic()

            def record(success, error_code=None):
                return self.model_health.record(
                    profile.model_id,
                    success=success,
                    latency_ms=min(600000.0, max(0.0, (time.monotonic() - started) * 1000)),
                    error_code=error_code,
                )

            try:
                authorization = self.provider_policy.authorize(
                    worker,
                    f"multi-model {task_type}",
                )
                if authorization.get("allowed") is not True:
                    return {
                        "model_id": profile.model_id,
                        "provider": profile.provider,
                        "success": False,
                        "code": "provider_policy_denied",
                    }
                response = worker.generate(
                    prompt=prompt,
                    context=dict(context),
                    task_type=task_type,
                )
                if not isinstance(response, dict):
                    record(False, "invalid_provider_response")
                    return {
                        "model_id": profile.model_id,
                        "provider": profile.provider,
                        "success": False,
                        "code": "invalid_provider_response",
                    }
                content = response.get("content")
                if not isinstance(content, str) or not content.strip() or len(content) > self.MAX_MODEL_OUTPUT:
                    record(False, "invalid_or_oversized_model_output")
                    return {
                        "model_id": profile.model_id,
                        "provider": profile.provider,
                        "success": False,
                        "code": "invalid_or_oversized_model_output",
                    }
                if response.get("success", True) is not True:
                    record(False, "provider_reported_failure")
                    return {
                        "model_id": profile.model_id,
                        "provider": profile.provider,
                        "success": False,
                        "code": "provider_reported_failure",
                    }
                health_record = record(True)
                return {
                    "model_id": profile.model_id,
                    "provider": profile.provider,
                    "success": True,
                    "health_recorded": health_record.get("success") is True,
                    "content": redact_sensitive_text(content.strip()),
                    "metadata": redact_sensitive_value(response.get("metadata", {})),
                    "provider_scope": authorization.get("provider_scope"),
                }
            except ProviderAccessDenied as error:
                return {
                    "model_id": profile.model_id,
                    "provider": profile.provider,
                    "success": False,
                    "code": error.code,
                }
            except Exception:
                record(False, "provider_failed")
                return {
                    "model_id": profile.model_id,
                    "provider": profile.provider,
                    "success": False,
                    "code": "provider_failed",
                }

        if not parallel or len(selected) == 1:
            return [invoke(profile, worker) for profile, worker in selected]
        results = []
        with ThreadPoolExecutor(max_workers=min(len(selected), 4)) as executor:
            futures = [executor.submit(invoke, profile, worker) for profile, worker in selected]
            for future in as_completed(futures):
                results.append(future.result())
        return results

    @staticmethod
    def _score(item, prompt, task_type):
        content = item["content"].strip()
        prompt_terms = {value.casefold() for value in prompt.split() if len(value) >= 4}
        content_terms = {value.casefold() for value in content.split() if len(value) >= 4}
        relevance = min(30, len(prompt_terms & content_terms) * 3)
        length = min(20, len(content) // 120)
        coding_bonus = (
            min(30, sum(token in content for token in ("def ", "class ", "function ", "import ")) * 7)
            if task_type == "coding"
            else 0
        )
        return {
            **item,
            "score": 50 + relevance + length + coding_bonus,
            "reason": "deterministic relevance and completeness score",
        }

    def _prompt(self, prompt):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > self.MAX_PROMPT:
            raise ValueError(f"prompt must contain 1 to {self.MAX_PROMPT} characters")
        return redact_sensitive_text(prompt.strip())

    def _context(self, context):
        if not isinstance(context, dict) or len(context) > self.MAX_CONTEXT_KEYS:
            raise ValueError("context must be an object with at most 50 keys")
        try:
            encoded = json.dumps(context, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > self.MAX_CONTEXT_BYTES:
                raise ValueError("context exceeds the 64000-byte limit")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("context must contain bounded JSON-safe values") from exc
        return redact_sensitive_value(context)
