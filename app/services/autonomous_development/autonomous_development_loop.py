from __future__ import annotations

from typing import Any

from .worker.change_applier import ChangeApplier, FileChange
from .worker.development_code_generator import DevelopmentCodeGenerator
from .worker.development_planner import DevelopmentPlanner
from .worker.development_worker import DevelopmentWorker


class AutonomousDevelopmentLoop:
    """
    Coordinates the autonomous development components.

    Flow:

        inspect
        -> plan
        -> generate changes
        -> validate changes
        -> optionally apply
        -> validate workspace

    Repository modifications require execute=True.
    """

    def __init__(
        self,
        workspace: str,
        *,
        planner: DevelopmentPlanner | None = None,
        code_generator: DevelopmentCodeGenerator | None = None,
    ) -> None:
        self.worker = DevelopmentWorker(
            workspace,
            code_generator=code_generator,
        )

        self.planner = (
            planner
            or DevelopmentPlanner()
        )

        self.code_generator = (
            code_generator
            or self.worker.code_generator
        )

        self.change_applier = ChangeApplier(
            self.worker.boundary
        )

    def inspect_and_plan(
        self,
        goal: str,
    ) -> dict[str, Any]:
        workspace = self.worker.inspect()

        plan = self.planner.create_plan(
            goal,
            workspace,
        )

        return {
            "success": bool(
                plan.get("success")
            ),
            "goal": goal,
            "workspace": workspace,
            "plan": plan,
        }

    def prepare_changes(
        self,
        goal: str,
        plan: dict[str, Any],
        *,
        iteration: int = 1,
    ) -> dict[str, Any]:
        """
        Ask the configured development provider for changes.

        The provider receives the actual workspace files.
        Returned changes are converted into FileChange objects
        and validated before they can be applied.
        """

        generated = self.worker.generate_changes(
            goal=goal,
            iteration=iteration,
            context={
                "plan": plan,
            },
        )

        if not generated.get(
            "success",
            False,
        ):
            return {
                "success": False,
                "stage": "generate_changes",
                "provider": generated.get(
                    "provider"
                ),
                "code": generated.get(
                    "code",
                    "provider_failed",
                ),
                "message": generated.get(
                    "message",
                    "Development provider failed.",
                ),
            }

        raw_changes = generated.get(
            "changes"
        )

        if not isinstance(
            raw_changes,
            list,
        ):
            return {
                "success": False,
                "stage": "generate_changes",
                "code": "invalid_changes",
                "message": (
                    "Development provider did not "
                    "return a changes list."
                ),
            }

        try:
            changes = [
                self.change_applier.from_dict(
                    value
                )
                for value in raw_changes
            ]

            validated = self.change_applier.validate(
                changes
            )

        except Exception as exc:
            return {
                "success": False,
                "stage": "change_validation",
                "code": "unsafe_changes",
                "message": str(exc),
            }

        return {
            "success": True,
            "changes": [
                {
                    "path": change.path,
                    "reason": change.reason,
                    "old_content_present": (
                        change.old_content
                        is not None
                    ),
                    "new_content_size": len(
                        change.new_content
                    ),
                }
                for change in validated
            ],
            "_validated_changes": validated,
        }

    def execute_changes(
        self,
        changes: list[FileChange],
        *,
        execute: bool = False,
        iteration: int = 1,
    ) -> dict[str, Any]:
        if not execute:
            return {
                "success": True,
                "dry_run": True,
                "message": (
                    "Dry-run: no repository files "
                    "were modified."
                ),
                "changes": [
                    {
                        "path": change.path,
                        "reason": change.reason,
                    }
                    for change in changes
                ],
            }

        self.worker.begin_iteration(
            iteration
        )

        try:
            changed_files = (
                self.change_applier.apply(
                    changes
                )
            )
        except Exception as exc:
            return {
                "success": False,
                "dry_run": False,
                "code": "change_application_failed",
                "message": str(exc),
            }

        return {
            "success": True,
            "dry_run": False,
            "changed_files": changed_files,
        }

    def validate_changes(
        self,
        *,
        iteration: int = 1,
        command: tuple[str, ...] = (
            "python",
            "-m",
            "pytest",
            "-q",
        ),
    ) -> dict[str, Any]:
        if not any(
            item.number == iteration
            for item in self.worker.iterations
        ):
            self.worker.begin_iteration(
                iteration
            )

        result = self.worker.run_validation(
            iteration,
            command,
        )

        return self.worker.result(
            iteration
        )

    def develop_iteration(
        self,
        *,
        goal: str,
        plan: dict[str, Any],
        iteration: int = 1,
        execute: bool = False,
    ) -> dict[str, Any]:
        """
        Execute one bounded development iteration.

        Default is dry-run. Autonomous callers must explicitly
        enable execution after the generated changes have passed
        validation.
        """

        prepared = self.prepare_changes(
            goal,
            plan,
            iteration=iteration,
        )

        if not prepared.get(
            "success",
            False,
        ):
            return prepared

        changes = prepared.get(
            "_validated_changes",
            [],
        )

        execution = self.execute_changes(
            changes,
            execute=execute,
            iteration=iteration,
        )

        if not execution.get(
            "success",
            False,
        ):
            return {
                **execution,
                "prepared": prepared,
            }

        if not execute:
            return {
                "success": True,
                "stage": "dry_run",
                "prepared": prepared,
                "execution": execution,
            }

        validation = self.validate_changes(
            iteration=iteration,
        )

        return {
            "success": (
                validation.get(
                    "status"
                ) == "completed"
            ),
            "stage": "validation",
            "prepared": prepared,
            "execution": execution,
            "validation": validation,
        }
