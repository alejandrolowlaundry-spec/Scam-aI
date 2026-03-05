from __future__ import annotations
import re
from app.config import settings

# ── Double Thank You Signal ────────────────────────────────────────────────────

SIGNAL_DOUBLE_THANK_YOU = "SIGNAL_DOUBLE_THANK_YOU"

_GRATITUDE_RE = re.compile(r"\b(thank\s+you|thanks)\b", re.IGNORECASE)


def detect_double_thank_you(transcript: str, window_words: int = 30) -> dict | None:
    """Return detection info if the caller says 'thank you' twice within window_words."""
    if not transcript:
        return None
    words = transcript.split()
    positions = [
        len(transcript[: m.start()].split())
        for m in _GRATITUDE_RE.finditer(transcript)
    ]
    if len(positions) < 2:
        return None
    for i in range(len(positions) - 1):
        if positions[i + 1] - positions[i] <= window_words:
            return {
                "detected": True,
                "explanation": (
                    "Caller repeated gratitude twice in a short window "
                    "(possible scripted / unnatural response)."
                ),
            }
    return None


def apply_post_signals(result, transcript: str):
    """Apply rule-based signals on top of AI analysis and return updated result."""
    from app.schemas import FraudAnalysisResult, FraudSignals

    detection = detect_double_thank_you(transcript)
    if not detection:
        return result

    other_signals = (
        len(result.signals.pressure_tactics)
        + len(result.signals.keywords)
        + len(result.signals.script_match)
    )
    bump = 10 if other_signals > 0 else 5
    new_score = min(100, result.risk_score + bump)

    signals_dict = result.signals.model_dump()
    signals_dict["double_thank_you"] = True

    return FraudAnalysisResult(
        risk_score=new_score,
        risk_label=get_risk_label(new_score),
        fraud_label=get_fraud_label(new_score),
        reasons=result.reasons + [detection["explanation"]],
        signals=FraudSignals(**signals_dict),
        summary=result.summary,
        confidence=result.confidence,
    )


# ── Labels ─────────────────────────────────────────────────────────────────────

def get_risk_label(score: int) -> str:
    if score < settings.medium_risk_threshold:
        return "low"
    elif score < settings.high_risk_threshold:
        return "medium"
    return "high"


def get_fraud_label(score: int) -> str:
    if score < settings.medium_risk_threshold:
        return "Safe Customer"
    elif score < settings.high_risk_threshold:
        return "Suspicious"
    return "Confirmed Scam"


def get_hubspot_deal_status(fraud_label: str) -> str:
    mapping = {
        "Safe Customer": "Verified Customer",
        "Suspicious": "Needs Manual Review",
        "Confirmed Scam": "Scam / Fraud",
    }
    return mapping.get(fraud_label, "Needs Manual Review")
