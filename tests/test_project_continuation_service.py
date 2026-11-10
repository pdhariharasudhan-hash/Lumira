import json

from app.services.projects.project_continuation_service import ProjectContinuationService


class FakeBuilder:
    def build(self, idea):
        return {"status": "accept", "objective": idea}


class FakeExecutor:
    def execute(self, idea, builder):
        return {"status": "accept", "execution_order": ["apply requested change"]}


class FakeValidator:
    def validate(self, files):
        return {"valid": True, "errors": []}


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.prompt = None

    def chat(self, prompt, history=None):
        self.prompt = prompt
        assert history is None
        return self.response


class FakeWriter:
    def __init__(self):
        self.saved = None
        self.history_events = []

    def save(self, project_name, files, metadata):
        self.saved = (project_name, files, metadata)
        event = "project_continued" if metadata.get("continued_from") else "version_created"
        self.history_events.append((project_name, event, metadata))
        return f"generated/{project_name}/v2"


def _service(provider):
    writer = FakeWriter()
    service = ProjectContinuationService(
        provider_router=provider,
        builder=FakeBuilder(),
        executor=FakeExecutor(),
        validator=FakeValidator(),
        writer=writer,
    )
    return service, writer


def _source():
    return {
        "main.py": (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.get('/items')\ndef read_items(): return []\n"
            "@app.post('/items')\ndef create_item(): return {}\n"
            "@app.put('/items/{item_id}')\ndef update_item(item_id: int): return {}\n"
            "@app.delete('/items/{item_id}')\ndef delete_item(item_id: int): return {}\n"
        ),
        "requirements.txt": "fastapi\nuvicorn\n",
    }


def test_continuation_uses_existing_source_and_saves_next_version():
    original = _source()
    original["README.md"] = "# Existing project\n"
    updated = _source()
    updated["README.md"] = "# Updated project\n"
    provider = FakeProvider(json.dumps({"summary": "Added project dashboard notes.", "files": updated}))
    service, writer = _service(provider)

    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        original,
        "Add a dashboard page.",
    )

    assert result["success"] is True
    assert result["new_version"] == "v2"
    assert "Existing project" in provider.prompt
    assert writer.saved[1] == updated
    assert writer.saved[2]["continued_from"] == "v1"
    assert writer.saved[2]["instructions"] == ["Add a dashboard page."]
    assert writer.history_events[0][1] == "project_continued"


def test_continuation_rejects_provider_that_omits_existing_files():
    source = _source()
    source["README.md"] = "# Existing project\n"
    generated = _source()
    provider = FakeProvider(json.dumps({"summary": "Changed API.", "files": generated}))
    service, writer = _service(provider)

    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        source,
        "Add a feature.",
    )

    assert result["success"] is False
    assert result["code"] == "source_file_omitted"
    assert writer.saved is None
    assert writer.history_events == []


def test_continuation_rejects_invalid_generated_source_without_saving():
    provider = FakeProvider(json.dumps({"summary": "Broken code.", "files": {"main.py": "not python", "requirements.txt": "fastapi\nuvicorn\n"}}))
    service, writer = _service(provider)
    service.validator = type("InvalidValidator", (), {"validate": lambda self, files: {"valid": False, "errors": ["syntax"]}})()
    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        _source(),
        "Change the API.",
    )
    assert result["success"] is False
    assert result["code"] == "generated_code_invalid"
    assert writer.saved is None
    assert writer.history_events == []


def test_continuation_rejects_source_context_that_exceeds_v1_budget():
    provider = FakeProvider("{}")
    service, writer = _service(provider)
    files = _source()
    files["README.md"] = "x" * (service.MAX_SOURCE_CONTEXT_CHARS + 1)
    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        files,
        "Add a feature.",
    )
    assert result["success"] is False
    assert result["code"] == "project_context_too_large"
    assert writer.saved is None


def test_continuation_rejects_no_op_provider_response():
    source = _source()
    provider = FakeProvider(json.dumps({"summary": "No changes.", "files": source}))
    service, writer = _service(provider)
    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        source,
        "Add a dashboard page.",
    )
    assert result["success"] is False
    assert result["code"] == "no_project_changes_generated"
    assert writer.saved is None


def test_continue_latest_project_uses_discovered_latest_version(monkeypatch):
    from app.services.lifecycle.project_lifecycle_service import ProjectLifecycleService

    service = object.__new__(ProjectLifecycleService)
    service.discovery = type(
        "Discovery",
        (),
        {"get_project": lambda self, name: {"project": name, "latest": {"version": "v7"}}},
    )()
    calls = []
    monkeypatch.setattr(
        service,
        "continue_project_version",
        lambda project, version, instruction: calls.append((project, version, instruction)) or {"success": True},
    )

    result = service.continue_latest_project("expense_api", "Add a dashboard page.")

    assert result["success"] is True
    assert calls == [("expense_api", "v7", "Add a dashboard page.")]


def test_continuation_rejects_syntax_error_in_any_generated_python_file():
    generated = _source()
    generated["dashboard.py"] = "def broken(:\\n    pass\\n"
    provider = FakeProvider(json.dumps({"summary": "Added dashboard module.", "files": generated}))
    service, writer = _service(provider)
    result = service.continue_version(
        "expense_api",
        "v1",
        {"project": "expense_api", "idea": "build expense api", "features": [], "instructions": []},
        _source(),
        "Add a dashboard module.",
    )
    assert result["success"] is False
    assert result["code"] == "generated_code_invalid"
    assert writer.saved is None
