
import os


GENERATED_DIR = "generated"


def ensure_generated_dir() -> None:
    os.makedirs(GENERATED_DIR, exist_ok=True)