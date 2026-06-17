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

        project_folder = (

            Path(
                "generated"
            )

            / project_name

            / version
        )

        if not project_folder.exists():

            return {

                "success":
                False,

                "message":
                "project not found"
            }

        result = {}

        metadata_file = (

            project_folder
            / "metadata.json"
        )

        if metadata_file.exists():

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

        old_idea = (
            metadata.get(
                "idea",
                ""
            )
        )

        features = (
            metadata.get(
                "features",
                []
            )
        )

        instructions = (
            metadata.get(
                "instructions",
                []
            )
        )

        instruction = (
            instruction
            .strip()
            .lower()
        )

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

        generated = (

            CodeService()
            .generate(
                new_idea,
                {}
            )
        )

        save_location = (

            ProjectWriter()
            .save(

                generated[
                    "code_target"
                ],

                generated[
                    "files"
                ],

                {

                    "idea":
                    new_idea,

                    "instructions":
                    instructions,

                    "features":
                    features,

                    "project_type":
                    "api",

                    "entity":
                    generated[
                        "code_target"
                    ]
                }
            )
        )

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
            features
        }