from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field, model_validator


class ModeCandidate(BaseModel):
    mode_id: str

    raw_score: float = 0.0
    score: float = 0.0

    intent_score: float = 0.0
    domain_score: float = 0.0
    phrase_score: float = 0.0

    matched_keywords: List[str] = Field(
        default_factory=list
    )

    matched_intents: List[str] = Field(
        default_factory=list
    )

    matched_domains: List[str] = Field(
        default_factory=list
    )

    matched_phrases: List[str] = Field(
        default_factory=list
    )

    reasons: List[str] = Field(
        default_factory=list
    )

    is_primary: bool = False

    @model_validator(mode="after")
    def validate_contract(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                "ModeCandidate.score must be between 0.0 and 1.0."
            )

        return self


class ModeDetectionResult(BaseModel):
    input_text: str = ""

    candidates: List[ModeCandidate] = Field(
        default_factory=list
    )

    selected_mode: str = ""

    # Primary requested action extracted from the
    # user's sentence.
    #
    # Examples:
    #   "run my code" -> "run"
    #   "plan my workflow" -> "plan"
    #   "debug the API" -> "debug"
    #
    # This is intentionally separate from
    # ModeCandidate.intent_score because words such
    # as "code" or "development" may describe the
    # subject rather than the requested action.
    primary_action: str = ""

    primary_action_mode: str = ""

    primary_action_confidence: float = 0.0

    top_score: float = 0.0
    second_score: float = 0.0
    score_margin: float = 0.0

    raw_top_score: float = 0.0
    raw_second_score: float = 0.0
    raw_score_margin: float = 0.0

    ambiguous: bool = False

    detected_at: str = Field(
        default_factory=lambda:
        datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    )

    @model_validator(mode="after")
    def validate_contract(self):
        # ----------------------------------
        # Candidate score bounds
        # ----------------------------------

        if any(
            not 0.0 <= candidate.score <= 1.0
            for candidate in self.candidates
        ):
            raise ValueError(
                "All candidate scores must be between "
                "0.0 and 1.0."
            )

        # ----------------------------------
        # Primary candidate integrity
        # ----------------------------------

        primary_candidates = [
            candidate
            for candidate in self.candidates
            if candidate.is_primary
        ]

        if self.selected_mode:

            if len(primary_candidates) != 1:
                raise ValueError(
                    "A selected mode must have exactly "
                    "one primary candidate."
                )

            if (
                primary_candidates[0].mode_id
                != self.selected_mode
            ):
                raise ValueError(
                    "Primary candidate must match "
                    "selected_mode."
                )

        elif primary_candidates:

            raise ValueError(
                "An empty selected_mode cannot have "
                "a primary candidate."
            )

        # ----------------------------------
        # Ambiguity integrity
        # ----------------------------------

        if self.ambiguous and self.selected_mode:
            raise ValueError(
                "An ambiguous result cannot select a mode."
            )

        # ----------------------------------
        # Primary action integrity
        # ----------------------------------

        if bool(self.primary_action) != bool(
            self.primary_action_mode
        ):
            raise ValueError(
                "primary_action and "
                "primary_action_mode must either both "
                "be populated or both be empty."
            )

        if not (
            0.0
            <= self.primary_action_confidence
            <= 1.0
        ):
            raise ValueError(
                "primary_action_confidence must be "
                "between 0.0 and 1.0."
            )

        # ----------------------------------
        # Normalized score integrity
        # ----------------------------------

        if not (
            0.0
            <= self.top_score
            <= 1.0
        ):
            raise ValueError(
                "top_score must be between 0.0 and 1.0."
            )

        if not (
            0.0
            <= self.second_score
            <= 1.0
        ):
            raise ValueError(
                "second_score must be between "
                "0.0 and 1.0."
            )

        expected_score_margin = round(
            self.top_score
            - self.second_score,
            2,
        )

        if self.score_margin != expected_score_margin:
            raise ValueError(
                "score_margin must equal "
                "top_score - second_score."
            )

        # ----------------------------------
        # Raw score integrity
        # ----------------------------------

        expected_raw_margin = round(
            self.raw_top_score
            - self.raw_second_score,
            2,
        )

        if self.raw_score_margin != expected_raw_margin:
            raise ValueError(
                "raw_score_margin must equal "
                "raw_top_score - raw_second_score."
            )

        return self

    @property
    def top_candidate(self):
        if not self.candidates:
            return None

        return self.candidates[0]

    @property
    def second_candidate(self):
        if len(self.candidates) < 2:
            return None

        return self.candidates[1]

    @property
    def secondary_candidates(self):
        if len(self.candidates) < 2:
            return []

        return self.candidates[1:]
