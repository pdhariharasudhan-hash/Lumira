import os

import uvicorn

from app.main import app

print("🚀 Starting backend...")

if __name__ == "__main__":
    uvicorn.run(
        "run:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
        workers=1,
    )
