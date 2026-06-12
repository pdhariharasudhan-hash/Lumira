from pathlib import Path
import json


class ActivityFeedService:

    def __init__(self):

        self.feed_file = Path(
            "memory/activity_feed.json"
        )

        self.feed_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.feed_file.exists():

            self._write(
                []
            )

    def _read(self):

        content = (
            self.feed_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return []

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.feed_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def add_event(
        self,
        event: dict
    ):

        data = (
            self._read()
        )

        data.append(
            event
        )

        self._write(
            data
        )

        return {

            "success":
            True
        }

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