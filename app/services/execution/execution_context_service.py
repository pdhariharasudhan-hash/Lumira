from pathlib import Path
import json


class ExecutionContextService:

    def __init__(self):
        self.context_file = (
            Path("memory")
            / "execution_context.json"
        )

        self.context_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.context_file.exists():
            self._write({
                "current_goal": None,
                "active_project": None,
                "active_version": None,
                "current_stage": None,
                "last_command": None,
                "active_mode": None,
                "artifacts": []
            })

    def _read(self):

        with open(
            self.context_file,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def _write(self, data):

        with open(
            self.context_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2
            )

    def get_context(self):

        data = self._read()
        data.setdefault("active_mode", None)
        return data

    def set_mode(self, mode):

        data = self._read()
        data["active_mode"] = mode
        self._write(data)

    def set_goal(self, goal):

        data = self._read()

        data["current_goal"] = goal

        self._write(data)

    def set_project(self, project):

        data = self._read()

        data["active_project"] = project

        self._write(data)

    def set_version(self, version):

        data = self._read()

        data["active_version"] = version

        self._write(data)

    def set_stage(self, stage):

        data = self._read()

        data["current_stage"] = stage

        self._write(data)

    def set_last_command(self, command):

        data = self._read()

        data["last_command"] = command

        self._write(data)

    def clear_project(self):

        data = self._read()

        data["active_project"] = None
        data["active_version"] = None

        self._write(data)

    def add_artifact(self, artifact):

        data = self._read()

        data["artifacts"].append(
            artifact
        )

        self._write(data)

    def reset(self):

        self._write({
            "current_goal": None,
            "active_project": None,
            "active_version": None,
            "current_stage": None,
            "last_command": None,
            "active_mode": None,
            "artifacts": []
        })