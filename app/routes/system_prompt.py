from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.identity.system_prompt_service import SystemPromptService
router=APIRouter()
class PromptUpdate(BaseModel):
    user_instructions: str | None = Field(default=None,max_length=50_000)
    adaptive_instructions: str | None = Field(default=None,max_length=50_000)
@router.get('/system-prompt')
def get_system_prompt(): return SystemPromptService().get()
@router.put('/system-prompt')
def update_system_prompt(body: PromptUpdate):
    try: return SystemPromptService().update(user=body.user_instructions,adaptive=body.adaptive_instructions)
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc))
