from fastapi import APIRouter, HTTPException

from app.services.memory.memory_service import MemoryService, MemoryValidationError

router = APIRouter()
memory_service = MemoryService()


# ==========================
# CREATE / UPDATE MEMORY
# ==========================
@router.post("/memory")
def set_memory(payload: dict):
    try:
        key = payload.get("key")
        value = payload.get("value")

        if not key:
            raise MemoryValidationError("key is required")

        updated_memory = memory_service.update(key, value)

        return {
            "status": "ok",
            "data": {
                "key": key,
                "value": value
            }
        }

    except MemoryValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================
# GET SINGLE VALUE
# ==========================
@router.get("/memory/{key}")
def get_memory(key: str):
    try:
        value = memory_service.get_value(key)

        if value is None:
            raise HTTPException(status_code=404, detail="key not found")

        return {
            "status": "ok",
            "data": {
                "key": key,
                "value": value
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================
# GET ALL MEMORY
# ==========================
@router.get("/memory")
def get_all_memory():
    try:
        memory = memory_service.get_all()

        return {
            "status": "ok",
            "data": memory
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))