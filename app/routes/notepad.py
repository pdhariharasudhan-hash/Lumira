from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.notepad_service import NotepadService, NotepadValidationError
from app.services.persistence.atomic_json_store import PersistenceIntegrityError

router = APIRouter()


class NoteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=20000)


class NoteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=20000)


@router.get("/notepad")
def list_notes():
    try:
        notes = NotepadService().list_notes()
    except (NotepadValidationError, ValueError, PersistenceIntegrityError):
        raise HTTPException(status_code=503, detail="Notepad storage is unavailable")
    return {"success": True, "count": len(notes), "notes": notes}


@router.get("/notepad/search")
def search_notes(query: str, limit: int = 50):
    try:
        notes = NotepadService().search_notes(query, limit)
    except NotepadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Notepad storage is unavailable") from exc
    return {"success": True, "count": len(notes), "notes": notes}


@router.post("/notepad", status_code=201)
def create_note(request: NoteCreateRequest):
    try:
        note = NotepadService().create_note(request.title, request.content)
    except NotepadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Notepad storage is unavailable") from exc
    return {"success": True, "note": note}


@router.patch("/notepad/{note_id}")
def update_note(note_id: str, request: NoteUpdateRequest):
    try:
        note = NotepadService().update_note(
            note_id,
            **request.model_dump(exclude_unset=True),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except NotepadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Notepad storage is unavailable") from exc
    return {"success": True, "note": note}


@router.delete("/notepad/{note_id}")
def delete_note(note_id: str):
    try:
        NotepadService().delete_note(note_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except NotepadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, PersistenceIntegrityError) as exc:
        raise HTTPException(status_code=503, detail="Notepad storage is unavailable") from exc
    return {"success": True, "deleted": True, "note_id": note_id}
