import base64

from fastapi.testclient import TestClient

from app.main import app
from app.services.artifacts.artifact_manager_service import ArtifactManagerService
from app.services.providers.provider_registry import ProviderRegistry
from app.services.search.unified_search_service import UnifiedSearchService


def test_binary_artifacts_require_safe_type_extension_and_matching_signature(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    png = b"\x89PNG\r\n\x1a\nminimal"
    saved = client.post(
        "/artifacts/binary",
        json={"type": "images", "extension": "PNG", "content_base64": base64.b64encode(png).decode()},
    )
    assert saved.status_code == 201
    artifact = saved.json()["artifact"]
    assert "file" not in artifact
    content = client.get(f"/artifacts/{artifact['artifact_id']}/content")
    assert content.status_code == 200
    assert content.content == png
    listed = client.get("/artifacts").json()["artifacts"]
    assert all("file" not in item for item in listed)

    malformed = client.post(
        "/artifacts/binary",
        json={"type": "images", "extension": "png", "content_base64": base64.b64encode(b"not an image").decode()},
    )
    executable = client.post(
        "/artifacts/binary",
        json={"type": "generated_files", "extension": "exe", "content_base64": base64.b64encode(b"MZ executable").decode()},
    )
    assert malformed.status_code == 400
    assert executable.status_code == 400
    stored_artifacts = ArtifactManagerService().get_all_artifacts()
    assert len(stored_artifacts) == 1
    assert stored_artifacts[0]["artifact_id"] == artifact["artifact_id"]


def test_report_generator_persists_searchable_outline_and_video_is_truthfully_unavailable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    report = client.post("/command", json={"input": "Write a report about PCB manufacturing"})
    assert report.status_code == 200
    report_result = report.json()["result"]
    assert report_result["success"] is True
    assert report_result["document"]["status"] == "outline_only"
    assert report_result["artifact"]["type"] == "reports"
    assert report_result["artifact"]["artifact_id"] in report.json()["context"]["recent_artifact_ids"]
    search = UnifiedSearchService().search_all("PCB manufacturing")
    assert any(item.get("artifact_id") == report_result["artifact"]["artifact_id"] for item in search["artifacts"])

    video = client.post("/command", json={"input": "Generate a video about PCB manufacturing"})
    assert video.status_code == 200
    assert video.json()["result"]["code"] == "provider_unavailable"
    assert video.json()["success"] is False


def test_binary_service_checks_signatures_without_route_mediation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = ArtifactManagerService()

    try:
        manager.create_binary_artifact("pdf", b"not a pdf", "test", "pdf")
    except ValueError as error:
        assert "signature" in str(error)
    else:
        raise AssertionError("invalid PDF bytes were stored")
    assert manager.get_all_artifacts() == []


def test_text_artifacts_cannot_impersonate_audio_or_rendered_images(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = ArtifactManagerService()

    for artifact_type, extension in (("audio", "wav"), ("images", "png")):
        try:
            manager.create_artifact(artifact_type, "not validated binary content", "test", extension)
        except ValueError as error:
            assert "binary content" in str(error).lower()
        else:
            raise AssertionError(f"text content was incorrectly stored as {artifact_type}")

    assert manager.get_all_artifacts() == []


def test_configured_video_provider_runs_through_command_and_persists_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class VideoProvider:
        provider_scope = "local"
        def generate(self, prompt):
            assert prompt == "Generate a video about Saturn"
            return {"success": True, "content": b"\x00\x00\x00\x00ftypisom", "extension": "mp4"}

    ProviderRegistry.register("video_generation", VideoProvider())
    try:
        result = TestClient(app).post("/command", json={"input": "Generate a video about Saturn"})
    finally:
        ProviderRegistry.clear()

    assert result.status_code == 200
    capability = result.json()["result"]
    assert capability["success"] is True
    artifact = ArtifactManagerService().get_artifact(capability["artifact"]["artifact_id"])
    assert artifact["type"] == "video"
    assert open(artifact["file"], "rb").read() == b"\x00\x00\x00\x00ftypisom"


def test_artifact_detail_reports_content_availability_without_exposing_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    created = client.post(
        "/artifacts",
        json={
            "type": "transcripts",
            "content": "A durable meeting transcript",
            "source": "voice capture",
            "extension": "txt",
        },
    )
    assert created.status_code == 201
    artifact = created.json()["artifact"]

    details = client.get(f"/artifacts/{artifact['artifact_id']}")
    assert details.status_code == 200
    public = details.json()["artifact"]
    assert public["content_available"] is True
    assert "file" not in public
    assert "content_available" not in artifact

def test_legacy_image_generation_never_saves_a_json_spec_as_an_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from app.services.generator.generator_capability_service import GeneratorCapabilityService
    from app.services.resources.resource_budget_service import ResourceBudgetService

    png = b"\x89PNG\r\n\x1a\nreal-image-bytes"

    class ImageProvider:
        provider_scope = "local"
        def generate(self, prompt, image_type):
            assert prompt == "A red rocket flying over Earth"
            assert image_type == "image"
            return {"success": True, "content": png, "extension": "png"}

    monkeypatch.setattr(
        ResourceBudgetService,
        "execution_guidance",
        lambda self: {"resource_pressure": "normal", "defer_optional_heavy_media_work": False},
    )
    ProviderRegistry.register("image_generation", ImageProvider())
    try:
        result = GeneratorCapabilityService().image_generation("A red rocket flying over Earth")
    finally:
        ProviderRegistry.clear()

    assert result["success"] is True
    assert result["artifact"]["type"] == "images"
    assert result["artifact"]["file"].endswith(".png")
    assert open(result["artifact"]["file"], "rb").read() == png
