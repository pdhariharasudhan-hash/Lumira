from fastapi.testclient import TestClient
from app.main import app

def test_command_greeting_returns_a_real_message():
    response=TestClient(app).post('/command',json={'input':'Hello, Lumira'})
    assert response.status_code==200
    body=response.json()
    assert body['success'] is True
    assert body['message']
    assert body['result']['capability']=='greeting'
