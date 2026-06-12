from fastapi import APIRouter
from pydantic import BaseModel

from app.services.project_writer import (
    ProjectWriter
)

from app.services.code_service import (
    CodeService
)

from app.services.feature_detector import (
    FeatureDetector
)

from app.routes.project_details import (
    get_project
)


router = APIRouter()


class ContinueRequest(
    BaseModel
):
    project: str
    version: str
    instruction: str


@router.post(
    "/continue_project"
)
def continue_project(
    request: ContinueRequest
):


    existing = get_project(
        request.project,
        request.version
    )


    if not existing["success"]:

        return existing


    metadata = (
        existing["data"]
        ["metadata"]
    )


    old_idea = metadata.get(
        "idea",
        ""
    )


    features = metadata.get(
        "features",
        []
    )


    instructions = metadata.get(
        "instructions",
        []
    )


    instruction = (
        request.instruction
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

        "previous":
        f"{request.project}/{request.version}",

        "saved_to":
        save_location,

        "new_idea":
        new_idea,

        "instructions":
        instructions,

        "features":
        features
    }