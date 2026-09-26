from pathlib import Path
from typing import Dict, List
import json

from app.services.projects.project_discovery_service import (
    ProjectDiscoveryService
)

from app.services.memory.memory_service import (
    MemoryService
)

from app.services.artifacts.artifact_manager_service import (
    ArtifactManagerService
)


from app.services.history.pipeline_history_service import PipelineHistoryService
from app.services.sessions.session_manager_service import SessionManagerService


class UnifiedSearchService:

    def __init__(self):

        self.projects = (
            ProjectDiscoveryService()
        )

        self.memory = (
            MemoryService()
        )

        self.artifacts = (
            ArtifactManagerService()
        )

        self.pipeline_history = PipelineHistoryService()
        self.sessions = SessionManagerService()

    # ==========================
    # PROJECT SEARCH
    # ==========================

    def search_projects(
        self,
        query: str
    ) -> List[Dict]:

        query = query.lower()

        results = []

        projects = (
            self.projects
            .get_projects()
        )

        for project in projects:

            latest = (
                project.get(
                    "latest"
                )
                or {}
            )

            searchable = " ".join([

                str(
                    latest.get(
                        "entity",
                        ""
                    )
                ),

                str(
                    latest.get(
                        "idea",
                        ""
                    )
                ),

                str(
                    latest.get(
                        "project_type",
                        ""
                    )
                )
            ]).lower()

            if query in searchable:

                results.append(
                    project
                )

        return results

    # ==========================
    # ARTIFACT SEARCH
    # ==========================

    def search_artifacts(
        self,
        query: str
    ) -> List[Dict]:

        query = query.lower()

        results = []

        artifacts = (
            self.artifacts
            .get_all_artifacts()
        )

        for artifact in artifacts:

            searchable = " ".join([

                str(
                    artifact.get(
                        "artifact_id",
                        ""
                    )
                ),

                str(
                    artifact.get(
                        "type",
                        ""
                    )
                ),

                str(
                    artifact.get(
                        "source",
                        ""
                    )
                ),

                str(
                    artifact.get(
                        "file",
                        ""
                    )
                )
            ]).lower()

            if query in searchable:

                results.append(
                    artifact
                )

        return results

    # ==========================
    # MEMORY SEARCH
    # ==========================

    def search_memory(
        self,
        query: str
    ):

        query = query.lower()

        memory = (
            self.memory
            .get_all()
        )

        memory_text = json.dumps(
            memory,
            ensure_ascii=False
        ).lower()

        if query in memory_text:

            return memory

        return {}

    # ==========================
    # PIPELINE HISTORY SEARCH
    # ==========================

    def search_pipeline_history(
        self,
        query: str
    ) -> List[Dict]:

        if not isinstance(query, str):
            return []

        query = query.strip()

        if not query:
            return []

        return self.pipeline_history.search(
            query
        )

    # ==========================
    # FEATURE HISTORY SEARCH
    # ==========================

    def search_feature_history(
        self,
        query: str
    ) -> List[Dict]:

        query = query.lower()

        results = []

        history = (
            self.memory
            .get_feature_history()
        )

        for record in history:

            searchable = json.dumps(
                record,
                ensure_ascii=False
            ).lower()

            if query in searchable:

                results.append(
                    record
                )

        return results

    # ==========================
    # GLOBAL SEARCH
    # ==========================

    def search_all(
        self,
        query: str
    ):

        structured_memory = self.memory.get_all()

        return {

            "projects":
            self.search_projects(
                query
            ),

            "artifacts":
            self.search_artifacts(
                query
            ),

            "memory":
            self.search_memory(
                query
            ),

            "feature_history":
            self.search_feature_history(
                query
            ),

            "pipeline_history":
            self.search_pipeline_history(
                query
            ),

            "sessions": self.search_sessions(query),

            "conversations": self.search_conversations(query),

            "goals": self._search_records(structured_memory.get("goals", []), query),

            "decisions": self._search_records(structured_memory.get("decisions", []), query),

            "experiences": self._search_records(structured_memory.get("experiences", []), query),

            "learning": self._search_records(structured_memory.get("learning_records", []), query),
        }

    @staticmethod
    def _search_records(records, query: str):
        query = query.strip().lower()
        if not query:
            return []
        return [
            record for record in records
            if query in json.dumps(record, ensure_ascii=False).lower()
        ]

    def search_sessions(self, query: str):
        query = query.strip().lower()
        if not query:
            return []
        return [
            session for session in self.sessions.list_sessions(limit=200)
            if query in json.dumps({key: value for key, value in session.items() if key != "cognitive_state"}, ensure_ascii=False).lower()
        ]

    def search_conversations(self, query: str):
        query = query.strip().lower()
        if not query:
            return []
        results = []
        for session in self.sessions.list_sessions(limit=200):
            conversation = {
                "session_id": session.get("session_id"),
                "conversation_id": session.get("conversation_id"),
                "summary": session.get("conversation", {}).get("summary", ""),
                "recent_messages": session.get("recent_messages", []),
            }
            if query in json.dumps(conversation, ensure_ascii=False).lower():
                results.append(conversation)
        return results