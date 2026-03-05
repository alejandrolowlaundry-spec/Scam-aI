"""
Fraud analysis service.

Provider selection (automatic):
  1. OpenAI GPT-4o  — if OPENAI_API_KEY is set
  2. Anthropic Claude — if CLAUDE_API_KEY is set
  3. Demo mode       — mock responses, no API calls
"""
from __future__ import annotations
import json
import re
from app.config import settings
from app.schemas import FraudAnalysisResult, FraudSignals
from app.utils.logging import logger

# ── Prompt (shared across providers) ──────────────────────────────────────────

SYSTEM_PROMPT = """You are a call verification analyst reviewing a recorded phone call transcript.
The call was an outbound order verification call made by the company to a customer.

VERIFICATION FLOW:
The AI asked the customer to confirm: (1) shipping address, (2) billing address,
and (3) the reason if addresses differ. The customer was expected to answer these questions.

DEFAULT OUTCOME — APPROVED:
The order should be APPROVED and the customer marked as Safe unless there is explicit refusal.
Any answer — even partial, vague, or brief — counts as cooperation. Do NOT penalize for:
- Short or simple answers
- Nervousness or hesitation
- Addresses being different (that is normal and expected)
- Any explanation given for address difference, no matter how simple
- Not knowing exact details by heart

MANUAL REVIEW REQUIRED — only if the customer:
- Explicitly refuses to answer ("I won't answer", "no", "I'm not telling you", "I refuse")
- Hangs up or ends the call before answering any question
- Provides no response at all to all three questions

Return ONLY valid JSON — no markdown, no commentary, no code fences."""

ANALYSIS_PROMPT = """Review this order verification call transcript.

CALL METADATA:
- Direction: {direction}
- From: {from_number}
- To: {to_number}
- Duration: {duration} seconds

TRANSCRIPT:
{transcript}

Determine the outcome:
- APPROVED (default): customer answered the verification questions in any way
- MANUAL REVIEW: customer explicitly refused to answer OR gave no response to any question

Return exactly this JSON schema:
{{
  "risk_score": <integer: 10 if approved, 55 if manual review>,
  "risk_label": <"low" if approved, "medium" if manual review>,
  "fraud_label": <"Safe Customer" if approved, "Suspicious" if manual review>,
  "reasons": [<1-3 short strings explaining the outcome>],
  "signals": {{
    "keywords": [],
    "pressure_tactics": [],
    "spoofing_suspected": false,
    "inconsistencies": [],
    "script_match": []
  }},
  "summary": "<1 sentence: state whether order was approved or flagged for manual review and why>",
  "confidence": <"low" | "medium" | "high">
}}"""


def _parse_result(raw_text: str) -> FraudAnalysisResult:
    text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    return FraudAnalysisResult(
        risk_score=data["risk_score"],
        risk_label=data["risk_label"],
        fraud_label=data["fraud_label"],
        reasons=data.get("reasons", []),
        signals=FraudSignals(**data.get("signals", {})),
        summary=data.get("summary", ""),
        confidence=data.get("confidence", "medium"),
    )


# ── OpenAI provider ────────────────────────────────────────────────────────────

async def _analyze_openai(prompt: str) -> FraudAnalysisResult:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_result(raw)


# ── Anthropic/Claude provider ──────────────────────────────────────────────────

async def _analyze_claude(prompt: str) -> FraudAnalysisResult:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.effective_claude_key)
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    return _parse_result(raw)


# ── Demo mocks ─────────────────────────────────────────────────────────────────

MOCK_MANUAL_REVIEW = FraudAnalysisResult(
    risk_score=55, risk_label="medium", fraud_label="Suspicious",
    reasons=[
        "Customer refused to answer verification questions",
        "No address information provided",
    ],
    signals=FraudSignals(
        keywords=[], pressure_tactics=[], spoofing_suspected=False,
        inconsistencies=[], script_match=[],
    ),
    summary="Customer explicitly refused to answer verification questions. Manual review required.",
    confidence="high",
)

MOCK_APPROVED = FraudAnalysisResult(
    risk_score=10, risk_label="low", fraud_label="Safe Customer",
    reasons=[
        "Customer confirmed shipping and billing addresses",
        "Cooperated with all verification questions",
    ],
    signals=FraudSignals(
        keywords=[], pressure_tactics=[], spoofing_suspected=False,
        inconsistencies=[], script_match=[],
    ),
    summary="Customer answered all verification questions. Order approved.",
    confidence="high",
)


# ── Public entry point ─────────────────────────────────────────────────────────

async def analyze_transcript(
    transcript: str,
    direction: str = "outbound",
    from_number: str = "unknown",
    to_number: str = "unknown",
    duration: int = 0,
) -> FraudAnalysisResult:
    if settings.demo_mode:
        refusal_words = ["refuse", "won't answer", "not telling", "no i won't", "i don't want to"]
        if any(w in transcript.lower() for w in refusal_words):
            return MOCK_MANUAL_REVIEW
        return MOCK_APPROVED

    prompt = ANALYSIS_PROMPT.format(
        direction=direction,
        from_number=from_number,
        to_number=to_number,
        duration=duration,
        transcript=transcript or "(no transcript available)",
    )

    try:
        if settings.openai_api_key:
            result = await _analyze_openai(prompt)
            provider = "openai"
        elif settings.effective_claude_key:
            result = await _analyze_claude(prompt)
            provider = "claude"
        else:
            logger.warning("no_ai_provider_configured")
            return MOCK_LOW_RISK

        from app.services.risk_scoring import apply_post_signals
        result = apply_post_signals(result, transcript)

        logger.info(
            "analysis_complete",
            provider=provider,
            risk_score=result.risk_score,
            fraud_label=result.fraud_label,
        )
        return result

    except json.JSONDecodeError as e:
        logger.error("ai_json_parse_error", error=str(e))
        raise ValueError(f"AI returned invalid JSON: {e}")
    except Exception as e:
        logger.error("ai_analysis_error", error=str(e))
        raise
