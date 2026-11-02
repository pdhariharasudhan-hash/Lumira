from fastapi.testclient import TestClient
from app.main import app

def test_system_prompt_route_exposes_layers():
    client=TestClient(app)
    response=client.get('/system-prompt')
    assert response.status_code==200
    body=response.json()
    assert body['protected_core']
    assert 'user_instructions' in body

def test_system_prompt_user_layer_can_update_without_overwriting_core():
    client=TestClient(app)
    before=client.get('/system-prompt').json()['protected_core']
    response=client.put('/system-prompt',json={'user_instructions':'Prioritize verified progress.'})
    assert response.status_code==200
    assert response.json()['protected_core']==before
