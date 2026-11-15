# Tamil, English, and mixed-language evaluation

Run the deterministic language regression checks with:

```powershell
python -m pytest -q tests/test_language_evaluation.py tests/test_language_detection_mixed.py tests/test_system_prompt_service.py
```

`LanguageEvaluationService.evaluate_detection()` runs the bundled synthetic corpus through Lumira's current language detector. The corpus covers English, Tamil Unicode, bounded romanized Tamil, romanized Tamil mixed with English, mixed Tamil and Latin scripts, and an empty input. The report contains counts, expected and detected labels, confidence, and opaque case IDs; it omits input text.

`evaluate_responses()` can score supplied provider responses against cases. It checks a heuristic output language label and caller-specified technical-term preservation. It does not call a model, retain responses, evaluate answer meaning, or claim Tamil fluency. Cases labeled `unknown` are marked for review and excluded from the scored denominator. Use synthetic examples for automated CI and obtain native-speaker review for semantic correctness, dialect coverage, transliteration ambiguity, and real transcription quality.

The language detector and its same-language system-prompt guidance remain separate from model capability: these checks verify those local contracts, not whether a particular local or cloud model follows them. Use opaque case IDs and do not put private conversation text in IDs or test reports.
