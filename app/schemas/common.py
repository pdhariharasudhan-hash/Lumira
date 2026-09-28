from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# -------------------------
# GENERIC INPUT (used by builder, validate)
# -------------------------
class GenericInput(BaseModel):
    input: str = Field(max_length=10000)
    session_id: Optional[str] = Field(default=None, max_length=128)
    workspace_id: str = Field(default="default", min_length=1, max_length=100)
    project_id: Optional[str] = Field(default=None, max_length=100)


# -------------------------
# VALIDATE
# -------------------------
class ValidateRequest(BaseModel):
    input: str = Field(max_length=10000)


# -------------------------
# BUILDER
# -------------------------
class BuilderRequest(BaseModel):
    input: str = Field(max_length=10000)


# -------------------------
# EXECUTE
# -------------------------
class ExecuteRequest(BaseModel):
    input: str = Field(max_length=10000)
    builder: Dict[str, Any]


# -------------------------
# CODE
# -------------------------
class CodeRequest(BaseModel):
    input: str = Field(max_length=10000)
    execute: Dict[str, Any]


# -------------------------
# MEMORY
# -------------------------
class MemoryGetRequest(BaseModel):
    key: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    key: str
    value: Any
