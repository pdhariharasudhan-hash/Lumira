from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes.research_library import router

def test_static_routes_precede_dynamic_research_id():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/research-library/recent")
    assert response.status_code != 422
