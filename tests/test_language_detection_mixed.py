from app.services.language.language_detection_service import LanguageDetectionService


def test_detects_tamil_english_mixed_script():
    result = LanguageDetectionService().detect("எனக்கு build a robot வேண்டும்")
    assert result["language"] == "ta-en"


def test_detects_romanized_tamil_mixed_with_english():
    result = LanguageDetectionService().detect("naan build a robot")
    assert result["language"] == "ta-en"
