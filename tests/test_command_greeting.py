from fastapi.testclient import TestClient
from app.main import app

def test_command_greeting_returns_a_real_message():
    response=TestClient(app).post('/command',json={'input':'Hello, Lumira'})
    assert response.status_code==200
    body=response.json()
    assert body['success'] is True
    assert body['message']
    assert body['result']['capability']=='greeting'


def test_vague_app_request_returns_a_clarifying_question():
    response = TestClient(app).post("/command", json={"input": "Build an app"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["clarification_required"] is True
    assert "What should the app help people do?" in body["message"]
    assert body["attachments"] == []
