import json

from app.services.output.user_output_adapter import adapt, build_message, collect_attachments


def _no_json(text: str):
    assert not text.lstrip().startswith(("{", "["))
    assert '"success"' not in text and "'success'" not in text


def test_image_result_becomes_message_and_image_attachment():
    response = {"success": True, "result": {"success": True, "capability": "generate_image",
                "artifact": {"artifact_id": "img-1", "type": "images"}}}
    out = adapt(response)
    _no_json(out["message"])
    assert out["attachments"] == [{"artifact_id": "img-1", "kind": "image", "type": "images",
                                   "title": "Images", "url": "/artifacts/img-1/content"}]
    assert "image" in out["message"]


def test_video_and_audio_kinds():
    result = {"capability": "x", "items": [{"artifact_id": "v", "type": "video"}, {"artifact_id": "a", "type": "audio"}]}
    kinds = {a["artifact_id"]: a["kind"] for a in collect_attachments(result)}
    assert kinds == {"v": "video", "a": "audio"}


def test_existing_message_is_preserved():
    out = adapt({"success": True, "message": "Hello. I am Lumira and I am ready.", "result": {"capability": "greeting"}})
    assert out["message"] == "Hello. I am Lumira and I am ready."


def test_failure_is_readable_not_json():
    msg = build_message({"success": False, "capability": "generate_image", "code": "invalid_prompt"})
    _no_json(msg)
    assert "invalid prompt" in msg


def test_search_summary():
    msg = build_message({"capability": "search", "results": {"projects": [1, 2], "artifacts": [3]}}, "search")
    assert msg.startswith("I found 3 matches")
    empty = build_message({"capability": "search", "results": {"projects": []}}, "search")
    assert "found nothing" in empty


def test_generic_result_never_dumps_dict():
    msg = build_message({"success": True, "capability": "growth_strategy", "status": "planned", "steps": [1, 2, 3]})
    _no_json(msg)
    assert "Growth strategy finished" in msg


def test_result_is_left_untouched_and_response_serializable():
    original = {"success": True, "result": {"capability": "voice_capture", "artifact": {"artifact_id": "a1", "type": "audio"}}}
    out = adapt(json.loads(json.dumps(original)))
    assert out["result"] == original["result"]
    json.dumps(out)


def test_non_dict_response_passes_through():
    assert adapt("raw") == "raw"
