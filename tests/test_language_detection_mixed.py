from app.services.language.language_detection_service import LanguageDetectionService


def test_detects_tamil_english_mixed_script():
    result = LanguageDetectionService().detect("எனக்கு build a robot வேண்டும்")
    assert result["language"] == "ta-en"


def test_detects_romanized_tamil_mixed_with_english():
    result = LanguageDetectionService().detect("naan build a robot")
    assert result["language"] == "ta-en"


def test_detects_pure_tamil_unicode_and_romanized_tamil():
    detector = LanguageDetectionService()
    assert detector.detect("வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்")["language"] == "ta"
    assert detector.detect("naan nalla irukken")["language"] == "ta"


def test_english_is_not_misclassified_as_tamil():
    assert LanguageDetectionService().detect("Please build a robot")["language"] == "en"
