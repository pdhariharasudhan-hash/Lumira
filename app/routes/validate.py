from typing import List

from fastapi import APIRouter

from app.schemas.common import GenericInput
from app.services.response_service import build_structured_response

router = APIRouter()


def unique_list(items: List[str]) -> List[str]:
    return list(dict.fromkeys(items))


def analyze_idea(content: str) -> dict:
    text = content.strip()
    lowered = text.lower()

    weaknesses: List[str] = []
    risks: List[str] = []

    if not text:
        return {
            "idea": "",
            "weaknesses": ["empty input"],
            "risks": ["no evaluation possible"],
            "verdict": "reject",
            "risk_level": "high"
        }

    words = text.split()
    word_count = len(words)

    junk_inputs = {
        "test",
        "hello",
        "hi",
        "hey",
        "demo",
        "check",
        "trial",
        "something",
        "anything",
        "project",
        "app",
        "ai"
    }

    vague_phrases = [
        "build something",
        "make something",
        "create something",
        "do project",
        "make app",
        "build app",
        "create app",
        "make ai",
        "build ai",
        "create ai"
    ]

    large_scope_keywords = [
        "full system",
        "everything",
        "all features",
        "complete ai",
        "entire system",
        "full assistant",
        "full ai assistant",
        "iron man ai"
    ]

    unrealistic_timeline_keywords = [
        "1 day",
        "2 days",
        "3 days",
        "1 week",
        "2 weeks"
    ]

    weak_hardware_keywords = [
        "4gb",
        "2gb",
        "low ram",
        "no gpu"
    ]

    distraction_keywords = [
        "voice",
        "ui",
        "frontend",
        "dashboard"
    ]

    core_keywords = [
        "memory",
        "api",
        "fastapi",
        "validator",
        "builder",
        "execute",
        "code",
        "cli"
    ]

    is_junk_input = lowered in junk_inputs
    has_vague_phrase = any(phrase in lowered for phrase in vague_phrases)
    has_large_scope = any(word in lowered for word in large_scope_keywords)
    has_unrealistic_timeline = any(word in lowered for word in unrealistic_timeline_keywords)
    has_weak_hardware = any(word in lowered for word in weak_hardware_keywords)
    has_jarvis = "jarvis" in lowered
    has_distraction = any(word in lowered for word in distraction_keywords)
    has_core_keyword = any(word in lowered for word in core_keywords)

    if is_junk_input:
        weaknesses.append("junk input")
        risks.append("no meaningful project signal")

    if word_count <= 2 and not has_core_keyword:
        weaknesses.append("idea too vague")
        risks.append("no clear direction")

    if word_count <= 3 and not has_core_keyword and not is_junk_input:
        weaknesses.append("idea too vague")
        risks.append("no clear direction")

    if has_vague_phrase:
        weaknesses.append("placeholder request")
        risks.append("unclear build target")

    if has_large_scope:
        weaknesses.append("scope too large")
        risks.append("project will not finish")

    if has_unrealistic_timeline:
        weaknesses.append("timeline unrealistic")
        risks.append("burnout or failure")

    if has_weak_hardware:
        weaknesses.append("insufficient hardware")
        risks.append("system will be slow or unusable")

    if has_jarvis:
        weaknesses.append("scope too large")
        risks.append("project will not finish")

    if has_distraction and not has_jarvis and not has_core_keyword:
        weaknesses.append("non-core feature")
        risks.append("wastes time before core is ready")

    if has_core_keyword:
        if "non-core feature" in weaknesses:
            weaknesses.remove("non-core feature")
        if "wastes time before core is ready" in risks:
            risks.remove("wastes time before core is ready")

    weaknesses = unique_list(weaknesses)
    risks = unique_list(risks)

    if is_junk_input:
        verdict = "reject"
        risk_level = "high"
    elif has_vague_phrase and not has_core_keyword:
        verdict = "reject"
        risk_level = "high"
    elif has_jarvis and has_unrealistic_timeline:
        verdict = "reject"
        risk_level = "high"
    elif "idea too vague" in weaknesses and len(weaknesses) == 1:
        verdict = "reject"
        risk_level = "high"
    elif len(weaknesses) == 0:
        verdict = "continue"
        risk_level = "low"
    elif len(weaknesses) <= 2:
        verdict = "high_risk"
        risk_level = "medium"
    else:
        verdict = "reject"
        risk_level = "high"

    return {
        "idea": text,
        "weaknesses": weaknesses,
        "risks": risks,
        "verdict": verdict,
        "risk_level": risk_level
    }


@router.post("/validate")
def validate_endpoint(payload: GenericInput):
    content = payload.input.strip()

    analysis = analyze_idea(content)

    status = "ok" if analysis["verdict"] in ["continue", "high_risk", "reject"] else "failed"

    result = {
        "received_input": content,
        "module": "validate",
        "action": "rule_based_validation",
        "result": analysis
    }

    return build_structured_response(
        endpoint="validate",
        status=status,
        data=result
    )