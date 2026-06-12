from datetime import datetime

from app.services.artifact_manager_service import (
    ArtifactManagerService
)


class ImageGenerationService:

    def __init__(self):

        self.artifacts = (
            ArtifactManagerService()
        )

    def generate(
        self,
        prompt: str,
        image_type: str = "image"
    ):

        supported_types = {

            "image",
            "diagram",
            "blueprint",
            "schematic"
        }

        if image_type not in supported_types:

            return {

                "success":
                False,

                "message":
                f"Unsupported image type: {image_type}"
            }

        artifact_content = (

            "[MOCK IMAGE GENERATION]\n\n"

            f"Prompt: {prompt}\n\n"

            f"Type: {image_type}\n\n"

            "Future versions will generate "
            "real visual artifacts.\n"

            "Current version stores the "
            "generation request and preserves "
            "history for traceability."
        )

        artifact_folder = {

            "image": "images",
            "diagram": "diagrams",
            "blueprint": "blueprints",
            "schematic": "schematics"
        }

        artifact = (

            self.artifacts
            .create_artifact(

                artifact_type=
                artifact_folder[
                    image_type
                ],

                content=
                artifact_content,

                source=
                "image_generation",

                extension=
                "txt"
            )
        )

        return {

            "success":
            True,

            "prompt":
            prompt,

            "image_type":
            image_type,

            "artifact":
            artifact,

            "created":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }