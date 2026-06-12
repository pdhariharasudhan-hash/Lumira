from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():

    return {
        "status": "ok",
        "services": {
            "validate": True,
            "builder": True,
            "execute": True,
            "code": True,
            "memory": True
        }
    }