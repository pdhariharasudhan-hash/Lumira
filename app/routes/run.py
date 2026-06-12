from fastapi import APIRouter

from app.schemas.common import (
    GenericInput
)

from app.services.builder_service import (
    BuilderService
)

from app.services.execute_service import (
    ExecuteService
)

from app.services.code_service import (
    CodeService
)

from app.services.project_writer import (
    ProjectWriter
)

router = APIRouter()


@router.post(
    "/run"
)
def run_pipeline(
    request: GenericInput
):

    idea = request.input


    validate = {

        "idea":
        idea,

        "weaknesses": [],

        "risks": [],

        "verdict":
        "continue",

        "risk_level":
        "low"
    }


    builder = (
        BuilderService()
        .build(
            idea
        )
    )


    execute = (
        ExecuteService()
        .execute(
            idea,
            builder
        )
    )


    code = (
        CodeService()
        .generate(
            idea,
            execute
        )
    )


    save_location = (
        ProjectWriter()
        .save(
            code[
                "code_target"
            ],

            code[
                "files"
            ],

            {
                "idea":
                idea,

                "project_type":
                "api",

                "entity":
                code[
                    "code_target"
                ]
            }
        )
    )


    return {

        "success":
        True,

        "endpoint":
        "run",

        "status":
        "ok",

        "data": {

            "validate":
            validate,

            "builder":
            builder,

            "execute":
            execute,

            "code":
            code,

            "saved_to":
            save_location
        }
    }