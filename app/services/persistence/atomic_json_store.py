import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterator


class PersistenceIntegrityError(ValueError):
    pass


class AtomicJsonStore:
    _lock = RLock()

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        """Serialize read-modify-write operations across Lumira processes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

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
            # A missing store has no state to serialize with a writer. Avoid
            # creating the parent directory and lock sidecar just to return a
            # caller-owned default; an overlapping first write linearizes
            # after this missing-file read.
            if not self.path.exists():
                return deepcopy(default)
            with self._process_lock():
                return self._read_unlocked(default)

    def read_or_create(self, default: Any) -> Any:
        """Read a store or atomically create it once without rewriting existing data."""
        with self._lock:
            with self._process_lock():
                if not self.path.exists():
                    self._write_unlocked(default)
                    return deepcopy(default)
                return self._read_unlocked(None)

    def write(self, value: Any) -> None:
        with self._lock:
            with self._process_lock():
                self._write_unlocked(value)

    def update(
        self,
        mutator: Callable[[Any], Any],
        default: Any = None,
        *,
        write_if_changed: bool = False,
    ) -> Any:
        """Run a serialized read-modify-write transaction.

        ``write_if_changed`` avoids unnecessary disk replacement for validation
        and schema-normalization callbacks that make no changes. The mutator
        must mutate the supplied document in place; its return value is still
        returned to the caller.
        """
        with self._lock:
            with self._process_lock():
                document = self._read_unlocked(default)
                original = deepcopy(document) if write_if_changed else None
                result = mutator(document)
                if not write_if_changed or document != original:
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
