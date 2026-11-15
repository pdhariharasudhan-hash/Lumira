import pytest

from app.services.language.language_evaluation_service import (
    LanguageEvaluationCase,
    LanguageEvaluationService,
)


def test_default_detection_suite_covers_english_tamil_and_mixed_language():
    report = LanguageEvaluationService().evaluate_detection()

    assert report["total"] >= 6
    assert report["passed"] == report["total"]
    assert report["failed"] == 0
    assert {result["expected"] for result in report["results"]} >= {"en", "ta", "ta-en"}
    assert report["quality_scope"] == "language_detection_proxy_only"


def test_detection_report_uses_case_ids_and_does_not_echo_input_text():
    case = LanguageEvaluationCase(
        case_id="private-sample",
        input_text="naan build confidential project",
        expected_language="ta-en",
    )

    report = LanguageEvaluationService().evaluate_detection([case])

    assert report["results"][0]["case_id"] == "private-sample"
    assert "input_text" not in report["results"][0]
    assert "confidential project" not in str(report)


def test_response_suite_checks_detected_language_and_preserved_terms():
    cases = [
        LanguageEvaluationCase(
            case_id="mixed-react",
            input_text="naan build React app pannunga",
            expected_language="ta-en",
            required_terms=("React",),
        ),
        LanguageEvaluationCase(
            case_id="english",
            input_text="Explain project checkpoints",
            expected_language="en",
        ),
    ]

    report = LanguageEvaluationService().evaluate_responses(
        {"mixed-react": "React app build pannalaam.", "english": "Project checkpoints divide work."},
        cases,
    )

    assert report["total"] == 2
    assert report["passed"] == 2
    assert report["results"][0]["required_term_count"] == 1
    assert report["results"][0]["missing_term_count"] == 0
    assert report["quality_scope"] == "language_form_proxy_only"
    assert "React app build pannalaam" not in str(report)
    assert "React" not in str(report)


def test_missing_mismatched_and_term_dropping_responses_are_reported_without_text():
    cases = [
        LanguageEvaluationCase(
            case_id="tamil",
            input_text="வணக்கம்",
            expected_language="ta",
            required_terms=("Lumira",),
        ),
        LanguageEvaluationCase(
            case_id="english",
            input_text="Build a project",
            expected_language="en",
        ),
    ]

    report = LanguageEvaluationService().evaluate_responses(
        {"tamil": "வணக்கம், நான் உதவுகிறேன்."},
        cases,
    )

    assert report["passed"] == 0
    assert report["failed"] == 2
    assert {result["status"] for result in report["results"]} == {"missing", "failed"}
    assert all("input_text" not in result for result in report["results"])
    assert "வணக்கம், நான் உதவுகிறேன்." not in str(report)


def test_invalid_cases_and_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="expected_language"):
        LanguageEvaluationCase(case_id="bad", input_text="hello", expected_language="fr")

    duplicate = LanguageEvaluationCase("same", "hello", "en")
    with pytest.raises(ValueError, match="duplicate"):
        LanguageEvaluationService().evaluate_detection([duplicate, duplicate])


def test_unknown_language_cases_require_review_instead_of_being_scored_as_passes():
    case = LanguageEvaluationCase("ambiguous", "", "unknown")

    report = LanguageEvaluationService().evaluate_responses({"ambiguous": ""}, [case])

    assert report["total"] == 0
    assert report["passed"] == 0
    assert report["review_required"] == 1
    assert report["results"][0]["status"] == "review_required"
