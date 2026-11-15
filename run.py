import os

import uvicorn

from app.main import app
from app.launch_config import validate_bind_host

print("🚀 Starting backend...")

if __name__ == "__main__":
    host = validate_bind_host(os.getenv("HOST", "127.0.0.1"))
    uvicorn.run(
        "run:app",
        host=host,
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        workers=1,
    )
