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


def test_document_and_source_code_artifacts_get_readable_output_kinds():
    result = {
        "items": [
            {"artifact_id": "doc-1", "type": "documents", "extension": "md", "title": "Project notes"},
            {"artifact_id": "code-1", "type": "generated_files", "extension": "py", "title": "main.py"},
            {"artifact_id": "bin-1", "type": "generated_files", "extension": "exe", "title": "installer"},
        ]
    }
    attachments = {item["artifact_id"]: item for item in collect_attachments(result)}
    assert attachments["doc-1"]["kind"] == "document"
    assert attachments["code-1"]["kind"] == "code"
    assert attachments["code-1"]["extension"] == "py"
    assert attachments["bin-1"]["kind"] == "file"


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


def test_nested_error_object_is_converted_to_plain_language():
    message = build_message({
        "success": False,
        "capability": "project_generation",
        "error": {"code": "project_save_failed", "message": "Disk is full."},
    })
    _no_json(message)
    assert message == "Project generation could not be completed: Disk is full."

def test_json_image_metadata_is_not_misrepresented_as_a_renderable_image():
    attachment = collect_attachments({
        "artifact": {
            "artifact_id": "image-spec",
            "type": "images",
            "extension": "json",
        }
    })[0]
    assert attachment["kind"] == "document"


def test_svg_diagrams_and_mp4_videos_keep_their_actual_media_types():
    attachments = collect_attachments({
        "items": [
            {"artifact_id": "diagram-svg", "type": "diagrams", "extension": "svg"},
            {"artifact_id": "movie-mp4", "type": "video", "extension": "mp4"},
            {"artifact_id": "wrong-image", "type": "images", "extension": "mp4"},
        ]
    })
    assert {item["artifact_id"]: item["kind"] for item in attachments} == {
        "diagram-svg": "image",
        "movie-mp4": "video",
        "wrong-image": "video",
    }



def test_adapter_creates_inline_image_output_descriptor():
    out = adapt({
        "success": True,
        "result": {"success": True, "capability": "image_generation",
                   "artifact": {"artifact_id": "img-inline", "type": "images", "title": "Circuit diagram"}},
    })
    assert out["output"] == {
        "type": "image",
        "url": "/artifacts/img-inline/content",
        "artifact_id": "img-inline",
        "title": "Circuit diagram",
    }
    assert "{" not in out["message"]


def test_adapter_creates_inline_video_and_audio_output_descriptors():
    video = adapt({"success": True, "result": {"artifact": {"artifact_id": "vid-1", "type": "video"}}})
    audio = adapt({"success": True, "result": {"artifact": {"artifact_id": "aud-1", "type": "audio"}}})
    assert video["output"]["type"] == "video"
    assert video["output"]["url"] == "/artifacts/vid-1/content"
    assert audio["output"]["type"] == "audio"
    assert audio["output"]["url"] == "/artifacts/aud-1/content"


def test_adapter_does_not_replace_existing_explicit_output():
    explicit = {"type": "text", "content": "The finished answer."}
    out = adapt({
        "success": True,
        "message": "The finished answer.",
        "output": explicit,
        "result": {"artifact": {"artifact_id": "img-2", "type": "images"}},
    })
    assert out["output"] == explicit


def test_non_media_artifacts_remain_attachments_without_becoming_primary_media():
    out = adapt({
        "success": True,
        "result": {"artifact": {"artifact_id": "doc-1", "type": "documents", "extension": "md"}},
    })
    assert "output" not in out
    assert out["attachments"][0]["kind"] == "document"


def test_unsolicited_json_message_is_replaced_with_its_readable_content():
    out = adapt({
        "success": True,
        "message": '{"message":"Here is the answer in normal language.","debug":true}',
        "result": {"capability": "conversation"},
    })

    assert out["message"] == "Here is the answer in normal language."
    _no_json(out["message"])


def test_unsolicited_json_without_readable_content_is_not_shown():
    out = adapt({
        "success": True,
        "message": '{"status":"completed","internal_count":3}',
        "result": {"capability": "conversation"},
    })

    _no_json(out["message"])
    assert "structured data" in out["message"]


def test_explicit_json_request_keeps_json_output():
    raw = '{"answer":"42","valid":true}'
    out = adapt(
        {"success": True, "message": raw, "result": {"capability": "conversation"}},
        prompt="Return the result as JSON.",
    )

    assert out["message"] == raw


def test_unsolicited_fenced_json_is_not_shown_as_the_answer():
    out = adapt({
        "success": True,
        "message": 'Here is the result:\n```json\n{"status":"completed"}\n```',
        "result": {"capability": "conversation"},
    })

    _no_json(out["message"])
    assert "structured data" in out["message"]


def test_negative_json_instruction_does_not_enable_json_output():
    raw = '{"status":"completed","internal_count":3}'
    out = adapt(
        {"success": True, "message": raw, "result": {"capability": "conversation"}},
        prompt="Do not return JSON. Answer in plain language.",
    )

    _no_json(out["message"])
    assert "structured data" in out["message"]


def test_prefixed_json_is_not_exposed_in_normal_chat():
    out = adapt({
        "success": True,
        "message": 'Here is the result: {"status":"completed","internal_count":3}',
        "result": {"capability": "conversation"},
    })

    assert out["message"] == "Here is the result."
    _no_json(out["message"])


def test_prefixed_json_with_readable_message_uses_the_message():
    out = adapt({
        "success": True,
        "message": 'Result: {"message":"The image is ready.","internal_count":3}',
        "result": {"capability": "conversation"},
    })

    assert out["message"] == "The image is ready."
    _no_json(out["message"])


def test_deeply_nested_json_string_fails_closed_in_normal_chat():
    raw = '{"message":' * 6 + '"internal state"' + '}' * 6
    out = adapt({
        "success": True,
        "message": raw,
        "result": {"capability": "conversation"},
    })

    _no_json(out["message"])
    assert "structured data" in out["message"]
