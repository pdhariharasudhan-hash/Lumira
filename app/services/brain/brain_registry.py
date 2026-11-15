"""
Deterministic registry for Lumira's Intelligence Layer modules.

The default constructor preserves the established twelve-stage pipeline.
Custom module sets and explicit registration support controlled composition
without allowing duplicate names or execution-order collisions.
"""
from __future__ import annotations

from threading import RLock
from typing import Iterable

from app.services.brain.brain_module import BrainModule
from app.services.conversation.conversation_module import ConversationModule
from app.services.goals.goal_module import GoalModule
from app.services.objective.objective_module import ObjectiveModule
from app.services.context.context_module import ContextModule
from app.services.constraints.constraint_module import ConstraintModule
from app.services.reasoning.reasoning_module import ReasoningModule
from app.services.decision.decision_module import DecisionModule
from app.services.planner.planner_module import PlannerModule
from app.services.prediction.prediction_module import PredictionModule
from app.services.verification.verification_module import VerificationModule
from app.services.reflection.reflection_module import ReflectionModule
from app.services.learning.learning_module import LearningModule


class BrainRegistry:
    """Thread-safe, deterministic registry of BrainModule instances."""

    MAX_MODULES = 12

    def __init__(self, modules: Iterable[BrainModule] | None = None) -> None:
        self._lock = RLock()
        defaults = [
            ConversationModule(), GoalModule(), ObjectiveModule(), ContextModule(),
            ConstraintModule(), ReasoningModule(), DecisionModule(), PlannerModule(),
            PredictionModule(), VerificationModule(), ReflectionModule(), LearningModule(),
        ]
        selected = defaults if modules is None else list(modules)
        self._modules: list[BrainModule] = []
        for module in selected:
            self.register_module(module)

    @staticmethod
    def _identity(module: BrainModule) -> tuple[str, int]:
        if not isinstance(module, BrainModule):
            raise TypeError("module must be an instance of BrainModule")
        name = module.name
        order = module.order
        if not isinstance(name, str) or not name.strip():
            raise ValueError("module name must be a non-empty string")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ValueError("module order must be a positive integer")
        if not callable(getattr(module, "execute", None)):
            raise ValueError("module must provide a callable execute method")
        return name.strip(), order

    def register_module(self, module: BrainModule, *, replace: bool = False) -> BrainModule:
        """Register a module; replacement must be explicitly requested."""
        name, order = self._identity(module)
        with self._lock:
            existing = next((item for item in self._modules if item.name == name), None)
            if existing is not None and not replace:
                raise ValueError(f"module already registered: {name}")
            if len(self._modules) >= self.MAX_MODULES and existing is None:
                raise ValueError(f"Brain pipeline cannot exceed {self.MAX_MODULES} modules")
            order_owner = next(
                (item for item in self._modules if item.order == order and item.name != name),
                None,
            )
            if order_owner is not None:
                raise ValueError(f"module order {order} is already used by {order_owner.name}")
            if existing is not None:
                self._modules.remove(existing)
            self._modules.append(module)
            self._modules.sort(key=lambda item: (item.order, item.name))
            return module

    def unregister_module(self, name: str) -> BrainModule | None:
        """Remove a module by its stable module name; return None if absent."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("module name must be a non-empty string")
        target = name.strip()
        with self._lock:
            for index, module in enumerate(self._modules):
                if module.name == target:
                    return self._modules.pop(index)
        return None

    def get_module(self, name: str) -> BrainModule | None:
        if not isinstance(name, str) or not name.strip():
            return None
        target = name.strip()
        with self._lock:
            return next((module for module in self._modules if module.name == target), None)

    def get_modules(self) -> list[BrainModule]:
        """Return a snapshot in deterministic execution order."""
        with self._lock:
            return list(self._modules)

    def get_module_names(self) -> list[str]:
        """Return class names in deterministic execution order (legacy API)."""
        with self._lock:
            return [module.__class__.__name__ for module in self._modules]

    def count(self) -> int:
        with self._lock:
            return len(self._modules)
