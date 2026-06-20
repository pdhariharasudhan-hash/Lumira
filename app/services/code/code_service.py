from typing import Dict, Any
import textwrap

from app.services.projects.project_classifier import (
    ProjectClassifier
)

from app.services.features.field_inference import (
    FieldInference
)

from app.services.features.feature_detector import (
    FeatureDetector
)

from app.services.templates.template_engine import (
    TemplateEngine
)

from app.services.code.naming_service import (
    NamingService
)


class CodeService:

    def generate(
        self,
        idea: str,
        execute: Dict[str, Any]
    ) -> Dict[str, Any]:

        classifier = (
            ProjectClassifier()
        )

        result = (
            classifier.classify(
                idea
            )
        )

        entity = result[
            "primary_entity"
        ]

        collection_name = (
            NamingService()
            .pluralize(
                entity
            )
        )

        fields = (
            FieldInference()
            .infer(
                entity
            )
        )

        features = (

            FeatureDetector()
            .detect(
                idea
            )
        )

        sections = (

            TemplateEngine()
            .get_sections(
                features
            )
        )

        parameter_string = ",\n    ".join(

            [

                f"{field}: str"

                for field in fields
            ]
        )

        object_string = ",\n            ".join(

            [

                f'"{field}": {field}'

                for field in fields
            ]
        )

        imports = "\n".join(

            sections[
                "imports"
            ]
        )

        globals_section = "\n".join(

            sections[
                "globals"
            ]
        )

        routes_section = "\n\n".join(

            sections[
                "routes"
            ]
        )

        requirements = [

            "fastapi",
            "uvicorn"
        ]

        requirements.extend(

            sections[
                "requirements"
            ]
        )

        requirements_text = "\n".join(

            sorted(
                set(
                    requirements
                )
            )
        )

        main_py = textwrap.dedent(

f"""
from fastapi import FastAPI

{imports}

app = FastAPI()


{collection_name} = []


{globals_section}


{routes_section}


@app.get(
    "/{collection_name}"
)
def get_items():

    return {collection_name}


@app.post(
    "/{collection_name}"
)
def create_item(
    {parameter_string}
):

    {collection_name}.append(

        {{
            {object_string}
        }}
    )

    return {{

        "success":
        True,

        "{collection_name}":
        {collection_name}
    }}


@app.put(
    "/{collection_name}/{{item_id}}"
)
def update_item(

    item_id: int,

    {parameter_string}
):

    if item_id >= len(
        {collection_name}
    ):

        return {{

            "success":
            False
        }}


    {collection_name}[item_id] = {{

        {object_string}
    }}


    return {{

        "success":
        True,

        "{collection_name}":
        {collection_name}
    }}


@app.delete(
    "/{collection_name}/{{item_id}}"
)
def delete_item(
    item_id: int
):

    if item_id >= len(
        {collection_name}
    ):

        return {{

            "success":
            False
        }}


    {collection_name}.pop(
        item_id
    )


    return {{

        "success":
        True
    }}

"""
        )

        return {

            "idea":
            idea,

            "code_target":
            f"{entity}_api",

            "files": {

                "main.py":
                main_py,

                "requirements.txt":
                requirements_text
            },

            "file_plan": [

                "main.py",

                "requirements.txt"
            ],

            "implementation_steps": [

                f"Create {entity} storage",

                "Create GET endpoint",

                "Create POST endpoint",

                "Create PUT endpoint",

                "Create DELETE endpoint"
            ],

            "test_steps": [

                "pip install -r requirements.txt",

                "uvicorn main:app --reload"
            ],

            "priority":
            "high",

            "status":
            "accept"
        }