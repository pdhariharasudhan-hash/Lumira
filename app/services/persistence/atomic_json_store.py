import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Callable


class PersistenceIntegrityError(ValueError):
    pass


class AtomicJsonStore:
    _lock = RLock()

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _read_unlocked(self, default: Any) -> Any:
        if not self.path.exists():
            return deepcopy(default)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PersistenceIntegrityError(
                f"Cannot read valid JSON from {self.path}"
            ) from exc

    def read(self, default: Any = None) -> Any:
        with self._lock:
            return self._read_unlocked(default)

    def write(self, value: Any) -> None:
        with self._lock:
            self._write_unlocked(value)

    def update(
        self,
        mutator: Callable[[Any], Any],
        default: Any = None,
    ) -> Any:
        with self._lock:
            document = self._read_unlocked(default)
            result = mutator(document)
            self._write_unlocked(document)
            return result

    def _write_unlocked(self, value: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                try:
                    json.dump(value, temporary_file, indent=2, ensure_ascii=False, allow_nan=False)
                except (TypeError, ValueError, RecursionError) as exc:
                    raise PersistenceIntegrityError("Stored data must be finite, JSON-compatible values") from exc
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()