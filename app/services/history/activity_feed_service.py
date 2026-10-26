from pathlib import Path
import json

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class ActivityFeedService:

    MAX_EVENTS = 1000

    def __init__(self):

        self.feed_file = Path(
            "memory/activity_feed.json"
        )

        self.feed_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        self.store = AtomicJsonStore(self.feed_file)

        if not self.feed_file.exists():

            self._write(
                []
            )

    def _read(self):
        data = self.store.read([])
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Activity feed must be a JSON list")
        return data[-self.MAX_EVENTS:]

    def _write(self, data):
        if not isinstance(data, list):
            raise PersistenceIntegrityError("Activity feed must be a JSON list")
        self.store.write(data[-self.MAX_EVENTS:])

    def add_event(self, event: dict):
        if not isinstance(event, dict):
            raise ValueError("Activity event must be an object")
        try:
            event_size = len(json.dumps(event, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("Activity event must contain JSON-compatible values") from exc
        if event_size > 25_000:
            raise ValueError("Activity event exceeds the 25000-byte limit")

        def append(data):
            if not isinstance(data, list):
                raise PersistenceIntegrityError("Activity feed must be a JSON list")
            data.append(event)
            del data[:-self.MAX_EVENTS]
            return True

        self.store.update(append, [])
        return {"success": True}

    def get_feed(
        self
    ):

        return self._read()

    def latest(
        self
    ):

        data = (
            self._read()
        )

        if not data:

            return None

        return data[-1]