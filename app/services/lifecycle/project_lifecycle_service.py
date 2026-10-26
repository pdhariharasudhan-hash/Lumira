from pathlib import Path
import json

from app.services.projects.project_discovery_service import (
    ProjectDiscoveryService
)

from app.services.workspace.workspace_service import (
    WorkspaceService
)

from app.services.projects.project_writer import (
    ProjectWriter
)

from app.services.code.code_service import (
    CodeService
)

from app.services.features.feature_detector import (
    FeatureDetector
)
from app.services.builder.builder_service import BuilderService
from app.services.execution.execute_service import ExecuteService
from app.services.validation.code_validation_service import CodeValidationService
from app.services.projects.project_paths import resolve_project_path


class ProjectLifecycleService:

    def __init__(
        self
    ):

        self.discovery = (
            ProjectDiscoveryService()
        )

        self.workspace = (
            WorkspaceService()
        )

    def list_projects(
        self
    ):

        return {

            "success":
            True,

            "projects":
            self.discovery.get_projects()
        }

    def get_project(
        self,
        project_name: str
    ):

        project = (
            self.discovery.get_project(
                project_name
            )
        )

        if not project:

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        return {

            "success":
            True,

            "project":
            project
        }

    def get_versions(
        self,
        project_name: str
    ):

        return {

            "success":
            True,

            "versions":
            self.discovery.get_versions(
                project_name
            )
        }

    def get_workspace_projects(
        self
    ):

        return (
            self.workspace
            .list_projects()
        )

    def get_project_version(
        self,
        project_name: str,
        version: str
    ):

        project_folder = resolve_project_path(project_name, version)

        if project_folder is None or not project_folder.is_dir():

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        result = {}
        total_bytes = 0

        metadata_file = (

            project_folder
            / "metadata.json"
        )

        if metadata_file.is_file():
            if metadata_file.stat().st_size > 100_000:
                return {"success": False, "message": "Project metadata exceeds the read limit"}
            if project_folder.resolve() not in metadata_file.resolve().parents:
                return {"success": False, "message": "Project metadata is outside the version directory"}

            with open(
                metadata_file,
                "r",
                encoding="utf-8"
            ) as f:

                result[
                    "metadata"
                ] = json.load(
                    f
                )

        files = {}

        for file in project_folder.iterdir():

            if (
                file.name
                ==
                "metadata.json"
            ):

                continue

            resolved_file = file.resolve()
            if project_folder.resolve() not in resolved_file.parents or not file.is_file():
                continue
            file_size = file.stat().st_size
            total_bytes += file_size
            if file_size > 2_000_000 or total_bytes > 10_000_000:
                return {"success": False, "message": "Project version exceeds the read limit"}

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                files[
                    file.name
                ] = f.read()

        result[
            "files"
        ] = files

        return {

            "success":
            True,

            "project":
            project_name,

            "version":
            version,

            "data":
            result
        }

    def continue_project(
        self,
        metadata: dict,
        instruction: str
    ):

        if not isinstance(metadata, dict) or not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 10000:
            return {"success": False, "status": "reject", "error": "A project and a non-empty instruction under 10000 characters are required."}

        old_idea = (
            metadata.get(
                "idea",
                ""
            )
        )
        if not isinstance(old_idea, str):
            return {"success": False, "status": "reject", "error": "Stored project idea is invalid."}

        stored_features = metadata.get("features", [])
        stored_instructions = metadata.get("instructions", [])
        if not isinstance(stored_features, list) or not all(isinstance(item, str) for item in stored_features):
            return {"success": False, "status": "reject", "error": "Stored project features are invalid."}
        if not isinstance(stored_instructions, list) or not all(isinstance(item, str) for item in stored_instructions):
            return {"success": False, "status": "reject", "error": "Stored project instructions are invalid."}
        features = list(stored_features)
        instructions = list(stored_instructions)

        instruction = instruction.strip().lower()

        instructions.append(
            instruction
        )

        new_features = (

            FeatureDetector()
            .detect(
                instruction
            )
        )

        for feature in new_features:

            if feature not in features:

                features.append(
                    feature
                )

        new_idea = (
            old_idea
            + " "
            + instruction
        ).strip()

        builder_result = BuilderService().build(new_idea)
        if builder_result.get("status") != "accept":
            return {"success": False, "status": builder_result.get("status", "refine"), "builder": builder_result}

        execution_result = ExecuteService().execute(new_idea, builder_result)
        if execution_result.get("status") != "accept":
            return {"success": False, "status": execution_result.get("status", "refine"), "builder": builder_result, "execution": execution_result}

        generated = (

            CodeService()
            .generate(
                new_idea,
                execution_result
            )
        )

        validation = CodeValidationService().validate(generated.get("files", {}))
        if not validation["valid"]:
            return {"success": False, "status": "reject", "validation": validation, "builder": builder_result, "execution": execution_result, "code": generated}

        project_name = metadata.get("project") or generated.get("code_target")
        if not isinstance(project_name, str) or not project_name.strip():
            return {"success": False, "status": "reject", "error": "Stored project name is invalid."}

        try:
            save_location = ProjectWriter().save(
                project_name,
                generated["files"],
                {
                    "idea": new_idea,
                    "instructions": instructions,
                    "features": features,
                    "project_type": "api",
                    "entity": project_name,
                    "project": project_name,
                    "builder": builder_result,
                    "execution": execution_result,
                    "validation": validation,
                },
            )
        except (OSError, ValueError) as error:
            return {"success": False, "status": "reject", "error": f"Project save failed: {error}", "builder": builder_result, "execution": execution_result, "validation": validation}

        return {

            "success":
            True,

            "saved_to":
            save_location,

            "new_idea":
            new_idea,

            "instructions":
            instructions,

            "features":
            features,

            "builder": builder_result,

            "execution": execution_result,

            "validation": validation
        }
