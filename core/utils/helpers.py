import re

from datetime import datetime, UTC

from typing import Any, List, Optional


STOPWORDS = {
    "the",
    "is",
    "at",
    "which",
    "on",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "of",
    "in",
    "with",
    "by",
    "from",
    "as",
    "it"
}


def now() -> str:

    return datetime.now(
        UTC
    ).isoformat()


def normalize_text(
    text: str
) -> str:

    return " ".join(
        text.strip().lower().split()
    )


def normalize_step(
    step: str
) -> str:

    return normalize_text(
        step
    )


def is_non_empty_string(
    value: Any
) -> bool:

    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def clean_string_list(
    values: Any
) -> Optional[List[str]]:

    if not isinstance(
        values,
        list
    ):
        return None

    if not values:
        return None

    cleaned: List[str] = []

    for item in values:

        if not is_non_empty_string(
            item
        ):
            return None

        cleaned.append(
            item.strip()
        )

    return cleaned


def extract_keywords(
    text: str
) -> List[str]:

    cleaned = re.sub(
        r"[^a-z0-9]",
        " ",
        text.lower()
    )

    words = cleaned.split()

    filtered = [
        word
        for word in words
        if word not in STOPWORDS
        and len(word) >= 4
    ]

    seen = set()

    keywords: List[str] = []

    for word in filtered:

        if word in seen:
            continue

        seen.add(
            word
        )

        keywords.append(
            word
        )

    priority_words = {
        "password",
        "username",
        "token",
        "secret",
        "auth",
        "apikey"
    }

    prioritized = []

    for word in keywords:

        if word in priority_words:

            prioritized.append(
                word
            )

    for word in keywords:

        if word not in prioritized:

            prioritized.append(
                word
            )

    return prioritized[:10]


def add_unique(
    items: List[str],
    value: str
) -> None:

    if value and value not in items:

        items.append(value)