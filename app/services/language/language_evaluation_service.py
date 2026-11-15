"""Deterministic, privacy-conscious language regression checks.

The evaluator measures the existing bounded language detector and simple
response-form proxies. It does not score translation correctness, fluency, or
semantic understanding; those require human review or a separately validated
evaluation model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from app.services.language.language_detection_service import LanguageDetectionService


SUPPORTED_LANGUAGES = frozenset({"en", "ta", "ta-en", "unknown"})
_CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_EXPECTED_RESPONSE_LANGUAGES = {
    "en": frozenset({"en"}),
    "ta": frozenset({"ta", "ta-en"}),
    "ta-en": frozenset({"ta-en"}),
}


@dataclass(frozen=True)
class LanguageEvaluationCase:
    """A caller-owned fixture; reports deliberately omit its text and terms."""

    case_id: str
    input_text: str
    expected_language: str
    required_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not _CASE_ID_PATTERN.fullmatch(self.case_id):
            raise ValueError("invalid_case_id")
        if not isinstance(self.input_text, str) or len(self.input_text) > 5_000:
            raise ValueError("invalid_input_text")
        if self.expected_language not in SUPPORTED_LANGUAGES:
            raise ValueError("invalid_expected_language")
        if not isinstance(self.required_terms, tuple) or len(self.required_terms) > 20:
            raise ValueError("invalid_required_terms")
        if any(not isinstance(term, str) or not term.strip() or len(term) > 120 for term in self.required_terms):
            raise ValueError("invalid_required_terms")


DEFAULT_LANGUAGE_CASES = (
    LanguageEvaluationCase("english-basic", "Explain a project checkpoint.", "en"),
    LanguageEvaluationCase("tamil-unicode", "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd", "ta"),
    LanguageEvaluationCase("tamil-romanized", "naan nalla irukken", "ta"),
    LanguageEvaluationCase("mixed-romanized", "naan build a robot pannunga", "ta-en"),
    LanguageEvaluationCase("mixed-script", "\u0ba8\u0bbe\u0ba9\u0bcd build project", "ta-en"),
    LanguageEvaluationCase("english-technical", "Explain React project checkpoints.", "en", ("React",)),
    LanguageEvaluationCase("empty-input", "", "unknown"),
)


class LanguageEvaluationService:
    """Evaluate deterministic language contracts without retaining sample text."""

    MAX_CASES = 100
    MAX_RESPONSE_CHARS = 20_000

    def __init__(self, detector: LanguageDetectionService | None = None):
        self.detector = detector or LanguageDetectionService()

    def evaluate_detection(
        self, cases: Iterable[LanguageEvaluationCase] | None = None
    ) -> dict:
        selected = self._validated_cases(cases)
        results = []
        for case in selected:
            detected = self.detector.detect(case.input_text)
            observed = detected.get("language", "unknown")
            results.append(
                {
                    "case_id": case.case_id,
                    "expected": case.expected_language,
                    "observed": observed,
                    "confidence": float(detected.get("confidence", 0.0)),
                    "passed": observed == case.expected_language,
                }
            )
        passed = sum(result["passed"] for result in results)
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "accuracy": passed / len(results),
            "quality_scope": "language_detection_proxy_only",
            "results": results,
        }

    def evaluate_responses(
        self,
        responses: Mapping[str, str],
        cases: Iterable[LanguageEvaluationCase] | None = None,
    ) -> dict:
        selected = self._validated_cases(cases)
        if not isinstance(responses, Mapping):
            raise ValueError("invalid_responses")
        case_ids = {case.case_id for case in selected}
        if any(not isinstance(key, str) or key not in case_ids for key in responses):
            raise ValueError("unknown_response_case")

        results = []
        for case in selected:
            if case.expected_language == "unknown":
                results.append(self._response_result(case, "review_required"))
                continue

            response = responses.get(case.case_id)
            if response is None:
                results.append(self._response_result(case, "missing"))
                continue
            if not isinstance(response, str) or len(response) > self.MAX_RESPONSE_CHARS:
                results.append(self._response_result(case, "invalid"))
                continue
            if not response.strip():
                results.append(self._response_result(case, "empty"))
                continue

            observed = self.detector.detect(response).get("language", "unknown")
            language_matched = observed in _EXPECTED_RESPONSE_LANGUAGES[case.expected_language]
            missing_terms = sum(term.casefold() not in response.casefold() for term in case.required_terms)
            passed = language_matched and missing_terms == 0
            results.append(
                {
                    "case_id": case.case_id,
                    "status": "passed" if passed else "failed",
                    "expected": case.expected_language,
                    "observed": observed,
                    "language_matched": language_matched,
                    "required_term_count": len(case.required_terms),
                    "missing_term_count": missing_terms,
                }
            )

        evaluated = [result for result in results if result["status"] in {"passed", "failed"}]
        passed = sum(result["status"] == "passed" for result in evaluated)
        denominator = len(results) - sum(result["status"] == "review_required" for result in results)
        return {
            "total": denominator,
            "passed": passed,
            "failed": denominator - passed,
            "review_required": sum(result["status"] == "review_required" for result in results),
            "missing": sum(result["status"] == "missing" for result in results),
            "empty": sum(result["status"] == "empty" for result in results),
            "invalid": sum(result["status"] == "invalid" for result in results),
            "quality_scope": "language_form_proxy_only",
            "results": results,
        }

    def _validated_cases(
        self, cases: Iterable[LanguageEvaluationCase] | None
    ) -> tuple[LanguageEvaluationCase, ...]:
        if cases is None:
            selected = DEFAULT_LANGUAGE_CASES
        else:
            if isinstance(cases, (str, bytes)):
                raise ValueError("invalid_cases")
            try:
                selected = tuple(cases)
            except TypeError as exc:
                raise ValueError("invalid_cases") from exc
        if not selected or len(selected) > self.MAX_CASES:
            raise ValueError("invalid_case_count")
        if any(not isinstance(case, LanguageEvaluationCase) for case in selected):
            raise ValueError("invalid_case")
        if len({case.case_id for case in selected}) != len(selected):
            raise ValueError("duplicate_case_id")
        return tuple(selected)

    @staticmethod
    def _response_result(case: LanguageEvaluationCase, status: str) -> dict:
        return {
            "case_id": case.case_id,
            "status": status,
            "expected": case.expected_language,
            "observed": None,
            "language_matched": None,
            "required_term_count": len(case.required_terms),
            "missing_term_count": None,
        }
