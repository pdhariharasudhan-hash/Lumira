from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes.research_library import router

def test_static_research_routes_are_not_shadowed():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/research-library/recent")
    assert response.status_code == 200
    response = client.get("/research-library/summary")
    assert response.status_code == 200
