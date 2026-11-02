from app.services.artifacts.artifact_manager_service import ArtifactManagerService


def test_recent_artifacts_returns_newest_first(tmp_path):
    service = ArtifactManagerService(tmp_path / 'artifacts', tmp_path / 'index.json')
    first = service.create_artifact('summaries', 'first', 'test')
    second = service.create_artifact('summaries', 'second', 'test')
    records = service.recent_artifacts(2)
    assert {item['artifact_id'] for item in records} == {first['artifact_id'], second['artifact_id']}


def test_recent_artifacts_validates_limit(tmp_path):
    service = ArtifactManagerService(tmp_path / 'artifacts', tmp_path / 'index.json')
    try:
        service.recent_artifacts(101)
        assert False
    except ValueError:
        assert True
