from datetime import datetime

from app.services.history.activity_feed_service import (
    ActivityFeedService
)


class EventLoggerService:

    def __init__(self):

        self.feed = (
            ActivityFeedService()
        )

    def log(
        self,
        event: str,
        source: str,
        data=None
    ):

        payload = {

            "event":
            event,

            "source":
            source,

            "data":
            data
            if data
            else {},

            "timestamp":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        self.feed.add_event(
            payload
        )

        return {

            "success":
            True
        }