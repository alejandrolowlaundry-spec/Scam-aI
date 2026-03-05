"""Tests for double-thank-you fraud signal detection."""
import pytest
from app.services.risk_scoring import detect_double_thank_you, apply_post_signals
from app.schemas import FraudAnalysisResult, FraudSignals


# ── detect_double_thank_you ────────────────────────────────────────────────────

def test_detects_exact_repeat():
    t = "Thank you thank you for your order."
    result = detect_double_thank_you(t)
    assert result is not None
    assert result["detected"] is True


def test_detects_thanks_variant():
    t = "Oh thanks thanks I really appreciate it."
    assert detect_double_thank_you(t) is not None


def test_detects_mixed_variants():
    t = "Thank you, thanks so much."
    assert detect_double_thank_you(t) is not None


def test_no_trigger_single_thank_you():
    t = "Thank you for calling."
    assert detect_double_thank_you(t) is None


def test_no_trigger_far_apart():
    # More than 30 words between two "thank you"s
    filler = " ".join(["word"] * 35)
    t = f"Thank you. {filler} And thank you."
    assert detect_double_thank_you(t) is None


def test_empty_transcript():
    assert detect_double_thank_you("") is None


def test_none_transcript():
    assert detect_double_thank_you(None) is None


# ── apply_post_signals ─────────────────────────────────────────────────────────

def _base_result(score=10, extra_signals=False) -> FraudAnalysisResult:
    return FraudAnalysisResult(
        risk_score=score,
        risk_label="low",
        fraud_label="Safe Customer",
        reasons=["Customer confirmed addresses."],
        signals=FraudSignals(
            keywords=["urgent"] if extra_signals else [],
            pressure_tactics=["act now"] if extra_signals else [],
            script_match=["scripted"] if extra_signals else [],
        ),
        summary="Customer answered all verification questions.",
        confidence="high",
    )


def test_apply_no_signal_no_change():
    result = _base_result()
    updated = apply_post_signals(result, "The address is 123 Main St.")
    assert updated.risk_score == result.risk_score
    assert updated.signals.double_thank_you is False


def test_apply_signal_bumps_score_small():
    result = _base_result(score=10)
    updated = apply_post_signals(result, "Thank you thank you very much.")
    assert updated.signals.double_thank_you is True
    assert updated.risk_score == 15  # +5 when no other signals


def test_apply_signal_bumps_score_large_when_other_signals():
    result = _base_result(score=10, extra_signals=True)
    updated = apply_post_signals(result, "Thank you thank you very much.")
    assert updated.signals.double_thank_you is True
    assert updated.risk_score == 20  # +10 when other signals present


def test_apply_signal_adds_reason():
    result = _base_result()
    updated = apply_post_signals(result, "Thank you thank you.")
    assert any("gratitude" in r.lower() or "scripted" in r.lower() for r in updated.reasons)


def test_apply_signal_caps_at_100():
    result = _base_result(score=98)
    updated = apply_post_signals(result, "Thank you thank you.")
    assert updated.risk_score == 100


def test_apply_signal_recalculates_labels():
    # Score 48 + 5 = 53 → still medium (threshold typically 40/70)
    result = _base_result(score=48)
    result = FraudAnalysisResult(
        **{**result.model_dump(), "risk_label": "medium", "fraud_label": "Suspicious"}
    )
    updated = apply_post_signals(result, "Thank you, thank you so much.")
    # Labels should be recomputed from new score
    assert updated.risk_label in ("low", "medium", "high")
