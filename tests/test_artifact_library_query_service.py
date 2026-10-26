from app.services.artifacts.artifact_library_query_service import ArtifactLibraryQueryService


class FakeArtifactManager:
    def __init__(self, records):
        self.records = records

    def get_all_artifacts(self):
        return list(self.records)


def test_artifact_search_uses_public_metadata_not_internal_file_paths():
    manager = FakeArtifactManager([
        {
            "artifact_id": "artifact-visible",
            "type": "transcripts",
            "source": "voice capture",
            "title": "Project meeting",
            "file": "/private/workspace/secret-project/transcript.txt",
            "archived": False,
        }
    ])
    service = ArtifactLibraryQueryService(manager)

    by_public_title = service.list_artifacts(query="project meeting")
    by_private_path = service.list_artifacts(query="secret-project")

    assert by_public_title["pagination"]["total"] == 1
    assert by_private_path["pagination"]["total"] == 0
    assert "file" not in by_public_title["artifacts"][0]


def test_artifact_search_is_case_insensitive_and_trims_query():
    manager = FakeArtifactManager([
        {
            "artifact_id": "artifact-1",
            "type": "summaries",
            "source": "voice",
            "title": "Tamil English planning",
            "archived": False,
        }
    ])

    result = ArtifactLibraryQueryService(manager).list_artifacts(query="  TAMIL english  ")

    assert result["pagination"]["total"] == 1
    assert result["artifacts"][0]["artifact_id"] == "artifact-1"


def test_artifact_query_keeps_pagination_bounded():
    service = ArtifactLibraryQueryService(FakeArtifactManager([]))

    for kwargs in ({"limit": 0}, {"limit": 501}, {"offset": -1}, {"offset": 100001}):
        try:
            service.list_artifacts(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid pagination accepted: {kwargs}")
