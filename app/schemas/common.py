from typing import Any, Dict, Optional
from pydantic import BaseModel


# -------------------------
# GENERIC INPUT (used by builder, validate)
# -------------------------
class GenericInput(BaseModel):
    input: str
    session_id: Optional[str] = None
    workspace_id: str = "default"
    project_id: Optional[str] = None


# -------------------------
# VALIDATE
# -------------------------
class ValidateRequest(BaseModel):
    input: str


# -------------------------
# BUILDER
# -------------------------
class BuilderRequest(BaseModel):
    input: str


# -------------------------
# EXECUTE
# -------------------------
class ExecuteRequest(BaseModel):
    input: str
    builder: Dict[str, Any]


# -------------------------
# CODE
# -------------------------
class CodeRequest(BaseModel):
    input: str
    execute: Dict[str, Any]


# -------------------------
# MEMORY
# -------------------------
class MemoryGetRequest(BaseModel):
    key: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    key: str
    value: Any