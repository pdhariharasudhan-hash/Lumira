from app.core.lumira_core import LumiraCore


def test_core_run_executes_builder_execution_code_and_atomic_save_once_in_order(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    builder_result = {"status": "accept", "steps": ["create storage", "create routes"]}
    execution_result = {"status": "accept", "builder": builder_result, "execution_order": ["step_1"], "task_steps": ["step_1"]}
    source = "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef read(): return {}\n@app.post('/')\ndef create(): return {}\n@app.put('/{item_id}')\ndef update(item_id: int): return {}\n@app.delete('/{item_id}')\ndef delete(item_id: int): return {}\n"
    code_result = {"status": "accept", "code_target": "task_api", "files": {"main.py": source, "requirements.txt": "fastapi"}}

    class Builder:
        def build(self, goal):
            calls.append(("builder", goal))
            return builder_result

    class Executor:
        def execute(self, goal, builder):
            calls.append(("execute", goal, builder))
            return execution_result

    class CodeGenerator:
        def generate(self, goal, execution):
            calls.append(("code", goal, execution))
            return code_result

    class Registry:
        services = {
            "builder": Builder(),
            "execute": Executor(),
            "code": CodeGenerator(),
        }

        def get(self, name):
            return self.services.get(name)

    core = LumiraCore.__new__(LumiraCore)
    core.registry = Registry()

    result = core.run("Build a task API")

    assert result == {
        "success": True,
        "status": "accept",
        "current_stage": "complete",
        "last_completed_stage": "save",
        "final_status": "completed",
        "retry_count": 0,
        "goal": "Build a task API",
        "builder": builder_result,
        "execution": execution_result,
        "code": code_result,
        "validation": {"success": True, "valid": True, "errors": []},
        "saved_to": str(tmp_path / "generated" / "task_api" / "v1"),
    }
    assert calls == [
        ("builder", "Build a task API"),
        ("execute", "Build a task API", builder_result),
        ("code", "Build a task API", execution_result),
    ]
    assert (tmp_path / "generated" / "task_api" / "v1" / "main.py").is_file()
