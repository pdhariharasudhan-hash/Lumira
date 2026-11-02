from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.documentation.project_documentation_service import ProjectDocumentationService

router = APIRouter(prefix="/project-documentation", tags=["Project Documentation"])
service = ProjectDocumentationService()

class DocumentationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=5000)
    components: list[str] = Field(default_factory=list, max_length=100)
    decisions: list[str] = Field(default_factory=list, max_length=100)

@router.post("/generate")
def generate(request: DocumentationRequest):
    try:
        return {"success": True, "documentation": service.generate(**request.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
