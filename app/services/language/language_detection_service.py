import re


class LanguageDetectionService:
    """Detect script plus a bounded lexicon of common romanized Tamil words."""

    TAMIL_ROMANIZED_TERMS = {
        "aama", "aamaam", "anga", "angey", "appo", "enna", "ennaku",
        "enakku", "enga", "engae", "epdi", "eppadi", "inga", "inge",
        "illa", "illai", "inniku", "iniku", "ippo", "iruka", "irukku",
        "irukkum", "kaami", "kaaminga", "kaatu", "kaattunga", "konjam",
        "nalla", "naalai", "naan", "naanga", "nee", "neenga", "oru", "paathu", "pannu",
        "pannalam", "pannalaam", "pannunga", "pannitu", "panra", "panren", "parunga", "po",
        "mudiyuma", "mudiyum", "venam", "romba", "sari", "seri", "sei", "seiya", "seiyunga", "sollu",
        "sollunga", "thodar", "thodaru", "thodarunga", "thedu",
        "thedunga", "vaa", "vaanga", "venum", "vendum", "yen",
        "yenna", "unga", "ungalukku",
    }

    def detect(self, text: str):
        if not isinstance(text, str) or not text.strip():
            return {"language": "unknown", "confidence": 0.0}

        tamil_found = any("\u0B80" <= char <= "\u0BFF" for char in text)
        ascii_tokens = re.findall(r"[a-z]+", text.lower())
        english_script_found = bool(ascii_tokens)

        # Tamil Unicode mixed with ASCII words is unambiguously mixed-script input.
        if tamil_found and english_script_found:
            return {"language": "ta-en", "confidence": 1.0}
        if tamil_found:
            return {"language": "ta", "confidence": 1.0}

        # Transliteration cannot be inferred perfectly. Use a bounded phrase lexicon,
        # and only label it mixed when at least one non-Tamil token is also present.
        tamil_tokens = [token for token in ascii_tokens if token in self.TAMIL_ROMANIZED_TERMS]
        if tamil_tokens:
            english_tokens = [token for token in ascii_tokens if token not in self.TAMIL_ROMANIZED_TERMS]
            if english_tokens:
                return {"language": "ta-en", "confidence": 0.85}
            return {"language": "ta", "confidence": 0.8}

        if english_script_found:
            return {"language": "en", "confidence": 1.0}
        return {"language": "unknown", "confidence": 0.0}
