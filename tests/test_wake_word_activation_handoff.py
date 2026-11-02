from app.services.voice.wake_word_listener_service import WakeWordListenerService


def test_wake_word_activation_handoff_is_fifo_and_bounded():
    listener = WakeWordListenerService(provider=object())
    listener._activation_events = [
        {"event": "wake_word_detected", "timestamp": "one"},
        {"event": "wake_word_detected", "timestamp": "two"},
    ]
    listener._detected_event.set()

    first = listener.consume_activation()
    second = listener.consume_activation()
    empty = listener.consume_activation()

    assert first["activated"] is True
    assert first["event"]["timestamp"] == "one"
    assert second["event"]["timestamp"] == "two"
    assert empty == {"success": True, "activated": False, "event": None}
    assert listener.wait_for_detection(0) is False
