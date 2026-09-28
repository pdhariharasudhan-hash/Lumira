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

    MAX_IDEA_LENGTH = 10000

    @staticmethod
    def _rejected(reason: str) -> Dict[str, Any]:
        return {
            "code_target": None,
            "files": {},
            "file_plan": [],
            "implementation_steps": [],
            "test_steps": [],
            "priority": "low",
            "status": "reject",
            "error": reason,
        }

    def generate(
        self,
        idea: str,
        execute: Dict[str, Any]
    ) -> Dict[str, Any]:

        if not isinstance(idea, str) or not idea.strip() or len(idea) > self.MAX_IDEA_LENGTH:
            return self._rejected("idea must contain 1 to 10000 characters")
        if not isinstance(execute, dict) or execute.get("status") != "accept":
            return self._rejected("code generation requires an accepted execution plan")
        execution_order = execute.get("execution_order")
        task_steps = execute.get("task_steps")
        if (
            not isinstance(execution_order, list)
            or not execution_order
            or len(execution_order) > 12
            or not all(isinstance(step, str) and step.strip() for step in execution_order)
            or not isinstance(task_steps, list)
            or not task_steps
            or len(task_steps) > 12
            or task_steps != execution_order
        ):
            return self._rejected("accepted execution plan must include ordered steps")

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

        visible_items = (
            "_get_records(current_user)"
            if "auth" in features
            else "_get_records()"
        )

        model_fields = "\n".join(f"    {field}: str = Field(max_length=5000)" for field in fields) or "    pass"
        record_expression = "payload.model_dump()"
        owner_expression = "current_user" if "auth" in features else "None"
        api_parameter = "payload: ItemPayload"
        auth_parameter = ""
        if "auth" in features:
            auth_parameter = "current_user: str = Depends(get_current_user)"

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

        routes_section = "\n\n".join(sections["routes"])
        routes_section = routes_section.replace("__COLLECTION__", collection_name)
        routes_section = routes_section.replace(
            "__VISIBLE_RECORDS__", visible_items
        )
        routes_section = routes_section.replace(
            "__AUTH_PARAMS__", ", current_user: str = Depends(get_current_user)"
            if "auth" in features else ""
        )
        routes_section = routes_section.replace(
            "(, current_user:", "(current_user:"
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
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import json
import os
import sqlite3
from pathlib import Path

{imports}

app = FastAPI()


DATA_DIR = Path(os.environ.get("LUMIRA_DATA_DIR", ".lumira_data")).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_FILE = Path(os.environ.get("LUMIRA_DATA_FILE", str(DATA_DIR / "{collection_name}.sqlite3"))).expanduser().resolve()
DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
MAX_RECORDS_PER_OWNER = 1000


class ItemPayload(BaseModel):
{model_fields}


def _connect():
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, payload TEXT NOT NULL)")
    connection.commit()
    return connection


def _get_records(owner=None):
    owner_key = owner or ""
    connection = _connect()
    try:
        rows = connection.execute("SELECT payload FROM records WHERE owner = ? ORDER BY id", (owner_key,)).fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        connection.close()


def _add_record(payload, owner=None):
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        count = connection.execute("SELECT COUNT(*) FROM records WHERE owner = ?", (owner or "",)).fetchone()[0]
        if count >= MAX_RECORDS_PER_OWNER:
            raise HTTPException(status_code=429, detail="record limit reached for this account")
        connection.execute("INSERT INTO records(owner, payload) VALUES (?, ?)", (owner or "", json.dumps(payload)))
        connection.commit()
    finally:
        connection.close()


def _update_record(item_id, payload, owner=None):
    if item_id < 0:
        return False
    owner_key = owner or ""
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("SELECT id FROM records WHERE owner = ? ORDER BY id", (owner_key,)).fetchall()
        if item_id >= len(rows):
            return False
        connection.execute("UPDATE records SET payload = ? WHERE id = ? AND owner = ?", (json.dumps(payload), rows[item_id][0], owner_key))
        connection.commit()
        return True
    finally:
        connection.close()


def _delete_record(item_id, owner=None):
    if item_id < 0:
        return False
    owner_key = owner or ""
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute("SELECT id FROM records WHERE owner = ? ORDER BY id", (owner_key,)).fetchall()
        if item_id >= len(rows):
            return False
        connection.execute("DELETE FROM records WHERE id = ? AND owner = ?", (rows[item_id][0], owner_key))
        connection.commit()
        return True
    finally:
        connection.close()


{globals_section}


{routes_section}


@app.get(
    "/{collection_name}"
)
def get_items(
    {auth_parameter}
):

    return {visible_items}


@app.post(
    "/{collection_name}"
)
def create_item(
    {api_parameter},
    {auth_parameter}
):
    _add_record({record_expression}, {owner_expression})

    return {{

        "success":
        True,

        "{collection_name}":
        {visible_items}
    }}


@app.put(
    "/{collection_name}/{{item_id}}"
)
def update_item(

    item_id: int,

    {api_parameter},
    {auth_parameter}
):
    if not _update_record(item_id, {record_expression}, {owner_expression}):
        return {{"success": False}}


    return {{

        "success":
        True,

        "{collection_name}":
        {visible_items}
    }}


@app.delete(
    "/{collection_name}/{{item_id}}"
)
def delete_item(
    item_id: int,
    {auth_parameter}
):

    if not _delete_record(item_id, {owner_expression}):
        return {{"success": False}}


    return {{

        "success":
        True
    }}

"""
        )

        files = {
            "main.py": main_py,
            "requirements.txt": requirements_text,
        }
        file_plan = ["main.py", "requirements.txt"]
        if "auth" in features:
            files["README.md"] = (
                "# Generated API\n\n"
                "## Authentication setup\n\n"
                "Registration and login accept JSON bodies. Passwords must be 12–256 characters; usernames are normalized to lowercase. "
                "The server stores salted PBKDF2 password hashes and a persistent signing key under `.lumira_auth/` by default. "
                "Set `LUMIRA_AUTH_DATA_DIR` to move that directory, or set `JWT_SECRET_KEY` to a stable secret of at least 32 bytes before starting the app. "
                "Do not commit either the data directory or the signing secret. Bearer tokens expire after one hour.\n\n"
                "API records are stored in SQLite under `.lumira_data/` by default and survive application restarts. "
                "Set `LUMIRA_DATA_DIR` to move the database directory or `LUMIRA_DATA_FILE` to select an explicit database file. "
                "Keep the database private; each authenticated record is scoped to its owner.\n"
            )
            file_plan.append("README.md")

        return {

            "idea":
            idea,

            "code_target":
            f"{entity}_api",

            "files": files,

            "file_plan": file_plan,

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
