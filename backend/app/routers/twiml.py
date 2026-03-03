"""
TwiML — production-grade state-machine address verification call.

States (stored as call_state["step"]):
  collect_shipping  → Ask for / extract shipping address
                      Also extract billing if the caller mentions it in the same turn.
  collect_billing   → Ask for / extract billing address
  ask_reason        → Addresses differ — ask why
  [done]            → Play confirmation, persist, end call

Python owns every state transition.
GPT-4o's only job per turn: extract the target field(s) + generate a short acknowledgment.

Call structure:
  /verification-call   → Play greeting (outside Gather)
                       → Gather plays ask_shipping → listen → /step/respond
  /step/respond (loop) → GPT-4o extracts + acks → next question inside Gather → listen
"""
from __future__ import annotations
import asyncio
import json
import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from openai import AsyncOpenAI
from sqlalchemy import select
from typing import Optional

from app.config import settings
from app.services import call_state, hubspot_service, elevenlabs_service
from app.database import AsyncSessionLocal
from app.models import Call
from app.utils.logging import logger

router = APIRouter()

# ── Fixed scripts (exact wording from spec) ───────────────────────────────────

_Q_SHIPPING   = "Could you please confirm the shipping address for the order?"
_Q_BILLING    = "Thank you. Could you also confirm the billing address used for the payment?"
_Q_REASON     = "I noticed the shipping and billing addresses are different. Could you briefly let me know why?"
_CONFIRMATION = "Perfect, thank you for confirming. Your order verification is complete and your order will proceed to shipping."


# ── Per-state GPT-4o prompts ──────────────────────────────────────────────────

def _prompt_collect_shipping() -> str:
    return """\
You are a verification specialist for Laundry Owners Warehouse on a phone call.
The caller just heard: "Could you please confirm the shipping address for the order?"

YOUR TASK: Extract the shipping address — and also the billing address if the caller mentions it.

EXTRACTION RULES (be very permissive — speech recognition may garble addresses):
- Extract the shipping address from whatever the caller says. If it contains numbers, street names, or location references, extract it as-is even if the phrasing seems garbled.
- If the caller also mentions a billing address (e.g. "same address", "same as shipping", "billing is 456 Oak Ave"), extract it too.
  * "same", "same address", or "same as shipping" → set billing_address = "SAME_AS_SHIPPING"
  * An actual different address → set billing_address to that address
- Only leave shipping_address empty if the caller is clearly talking about something completely unrelated OR explicitly refuses.
- If the caller explicitly refuses, set refused = true.

RESPONSE RULES:
- If shipping captured: acknowledge warmly in 1 sentence. Example: "Got it, thank you."
- If off_topic: acknowledge in 1 sentence, then redirect:
  "Of course. Just to complete the verification — could you confirm the shipping address?"
- If nothing captured: ask again gently: "Could you please confirm the shipping address?"
- If refused: polite 1-sentence closing.

Keep the response to 1–2 sentences. Sound warm and natural, not robotic.

Respond ONLY with valid JSON, no markdown:
{
  "response": "your spoken reply",
  "shipping_address": "extracted shipping address or empty string",
  "billing_address": "SAME_AS_SHIPPING, extracted billing address, or empty string",
  "off_topic": false,
  "refused": false
}"""


def _prompt_collect_billing(shipping: str) -> str:
    return f"""\
You are a verification specialist for Laundry Owners Warehouse on a phone call.
Shipping address already confirmed: {shipping}
The caller just heard: "Thank you. Could you also confirm the billing address used for the payment?"

YOUR TASK: Extract the billing address from the caller's response.

EXTRACTION RULES (be very permissive — speech recognition may garble addresses):
- "same", "same address", "same as shipping", "it's the same" → billing_address = "SAME_AS_SHIPPING"
- ANY response containing numbers, street names, city, or location references → extract as-is as billing_address
- If the speech seems garbled but contains address-like content (numbers + words), STILL extract it — do not reject imperfect speech
- Only leave billing_address empty if the caller is clearly talking about something completely unrelated (weather, products, etc.) OR explicitly refuses
- If the caller explicitly refuses (says "no", "I won't", "stop"), set refused = true

RESPONSE RULES:
- If billing captured: acknowledge in 1 sentence. Example: "Got it, thank you."
- If off_topic: 1-sentence acknowledge + redirect to billing address question.
- If nothing captured: ask again gently.
- If refused: polite 1-sentence closing.

Keep the response to 1–2 sentences.

Respond ONLY with valid JSON, no markdown:
{{
  "response": "your spoken reply",
  "billing_address": "SAME_AS_SHIPPING, extracted billing address, or empty string",
  "off_topic": false,
  "refused": false
}}"""


def _prompt_ask_reason(shipping: str, billing: str) -> str:
    return f"""\
You are a verification specialist for Laundry Owners Warehouse on a phone call.
Shipping address: {shipping}
Billing address: {billing}
The caller just heard: "I noticed the shipping and billing addresses are different. Could you briefly let me know why?"

YOUR TASK: Extract any explanation the caller gives for the address difference.

EXTRACTION RULES:
- Extract whatever reason or explanation the caller provides.
- Even a brief answer like "gift", "work address", or "different card" counts.
- If the caller is talking about something unrelated, set off_topic = true.
- If the caller explicitly refuses, set refused = true.

RESPONSE RULES:
- If reason captured: acknowledge in 1 sentence. Example: "Understood, thank you."
- If off_topic: acknowledge + redirect to asking why the addresses differ.
- If nothing captured: ask again gently.
- If refused: polite 1-sentence closing.

Keep the response to 1–2 sentences.

Respond ONLY with valid JSON, no markdown:
{{
  "response": "your spoken reply",
  "difference_reason": "the reason the caller gave, or empty string",
  "off_topic": false,
  "refused": false
}}"""


# ── TwiML helpers ─────────────────────────────────────────────────────────────

def _base_url(request: Request) -> str:
    return settings.public_url or str(request.base_url).rstrip("/")


def _gather(action: str, inner_xml: str, base_url: str) -> str:
    """
    speechTimeout="1"  — 1 second of silence after speech ends before submitting.
    timeout="10"       — wait up to 10 s for caller to start speaking.
    Redirect fires if total silence throughout.
    """
    return (
        f'<Gather input="speech" action="{base_url}{action}" method="POST" '
        f'speechTimeout="1" timeout="10" speechModel="phone_call">\n'
        f'    {inner_xml}\n'
        f'    <Pause length="2"/>\n'
        f'</Gather>\n'
        f'<Redirect method="POST">{base_url}{action}</Redirect>'
    )


def _xml(body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n{body}\n</Response>',
        media_type="application/xml",
    )


async def _audio(base_url: str, text: str, step_name: str | None = None) -> str:
    """
    Return a <Play> or <Say> XML fragment for the given text.

    Priority:
      1. Pre-cached ElevenLabs step audio (zero latency) — if step_name given
      2. Dynamically generated ElevenLabs audio (1–2 s latency)
      3. <Say> fallback (instant, Alice voice)
    """
    if not settings.elevenlabs_api_key or settings.demo_mode:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<Say voice="alice" language="en-US">{safe}</Say>'

    # Try pre-cached step audio first
    if step_name:
        try:
            audio_bytes = await elevenlabs_service.get_step_audio(step_name)
            key = str(uuid.uuid4())
            elevenlabs_service._dynamic_cache[key] = audio_bytes
            return f'<Play>{base_url}/audio/dynamic/{key}</Play>'
        except Exception:
            pass  # fall through to dynamic generation

    # Dynamic generation
    key = str(uuid.uuid4())
    success = await elevenlabs_service.cache_dynamic_audio(key, text)
    if success:
        return f'<Play>{base_url}/audio/dynamic/{key}</Play>'

    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<Say voice="alice" language="en-US">{safe}</Say>'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _addresses_same(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return " ".join(s.lower().strip().split())
    return norm(a) == norm(b)


def _resolve_billing(shipping: str, raw_billing: str) -> str:
    """Resolve 'SAME_AS_SHIPPING' token to the actual shipping address."""
    if raw_billing.upper() == "SAME_AS_SHIPPING":
        return shipping
    return raw_billing


# ── Core AI logic ─────────────────────────────────────────────────────────────

async def _call_gpt4o(system: str, messages: list[dict]) -> dict:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    completion = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": system}] + messages,
        max_tokens=200,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)


async def _ai_respond(call_sid: str, speech: str) -> dict:
    """
    State machine turn processor.

    Loads current state → calls GPT-4o with a focused per-state prompt →
    extracts field(s) → advances state → returns:
      { ack_text, next_question_text, next_step_audio, done, refused }
    """
    state  = call_state.load(call_sid)
    step   = state.get("step", "collect_shipping")
    shipping = state.get("shipping_address", "")
    billing  = state.get("billing_address", "")
    messages: list[dict] = list(state.get("messages", []))

    caller_text = speech.strip() if speech and speech.strip() else "(no response)"
    messages.append({"role": "user", "content": caller_text})

    logger.info("ai_turn", call_sid=call_sid, step=step,
                speech_preview=caller_text[:80])

    # ── COLLECT_SHIPPING ──────────────────────────────────────────────────────
    if step == "collect_shipping":
        try:
            result = await _call_gpt4o(_prompt_collect_shipping(), messages)
        except Exception as e:
            logger.error("gpt4o_failed", step=step, error=str(e))
            result = {"response": "I'm sorry, could you repeat that?",
                      "shipping_address": "", "billing_address": "",
                      "off_topic": False, "refused": False}

        ack      = result.get("response", "")
        refused  = bool(result.get("refused", False))
        ext_ship = (result.get("shipping_address") or "").strip()
        ext_bill = (result.get("billing_address") or "").strip()

        if refused:
            messages.append({"role": "assistant", "content": ack})
            call_state.save(call_sid, "messages", messages)
            return {"ack": ack, "next_q": "", "next_audio": None, "done": True, "refused": True}

        if ext_ship:
            call_state.save(call_sid, "shipping_address", ext_ship)
            shipping = ext_ship

            if ext_bill:
                resolved = _resolve_billing(shipping, ext_bill)
                call_state.save(call_sid, "billing_address", resolved)
                billing = resolved
                # Both captured in one turn → skip to comparison
                return await _after_both_captured(call_sid, shipping, billing, ack, messages)

            # Only shipping captured → ask billing
            call_state.save(call_sid, "step", "collect_billing")
            messages.append({"role": "assistant", "content": ack + " " + _Q_BILLING})
            call_state.save(call_sid, "messages", messages)
            return {"ack": ack, "next_q": _Q_BILLING, "next_audio": "ask_billing",
                    "done": False, "refused": False}

        # Fallback: if GPT-4o didn't extract but caller said something meaningful, accept raw
        if caller_text and caller_text != "(no response)" and len(caller_text.split()) >= 2:
            call_state.save(call_sid, "shipping_address", caller_text)
            shipping = caller_text
            call_state.save(call_sid, "step", "collect_billing")
            ack = "Got it, thank you."
            messages.append({"role": "assistant", "content": ack + " " + _Q_BILLING})
            call_state.save(call_sid, "messages", messages)
            return {"ack": ack, "next_q": _Q_BILLING, "next_audio": "ask_billing",
                    "done": False, "refused": False}

        # Nothing captured and nothing meaningful said
        messages.append({"role": "assistant", "content": ack})
        call_state.save(call_sid, "messages", messages)
        return {"ack": ack, "next_q": "", "next_audio": None, "done": False, "refused": False}

    # ── COLLECT_BILLING ───────────────────────────────────────────────────────
    if step == "collect_billing":
        try:
            result = await _call_gpt4o(_prompt_collect_billing(shipping), messages)
        except Exception as e:
            logger.error("gpt4o_failed", step=step, error=str(e))
            result = {"response": "I'm sorry, could you repeat that?",
                      "billing_address": "", "off_topic": False, "refused": False}

        ack     = result.get("response", "")
        refused = bool(result.get("refused", False))
        ext_bill = (result.get("billing_address") or "").strip()

        if refused:
            messages.append({"role": "assistant", "content": ack})
            call_state.save(call_sid, "messages", messages)
            return {"ack": ack, "next_q": "", "next_audio": None, "done": True, "refused": True}

        if ext_bill:
            resolved = _resolve_billing(shipping, ext_bill)
            call_state.save(call_sid, "billing_address", resolved)
            billing = resolved
            return await _after_both_captured(call_sid, shipping, billing, ack, messages)

        # Fallback: if GPT-4o didn't extract but caller actually said something
        # meaningful (not silence/no response), accept their raw speech as the address.
        if caller_text and caller_text != "(no response)" and len(caller_text.split()) >= 2:
            call_state.save(call_sid, "billing_address", caller_text)
            billing = caller_text
            ack = "Got it, thank you."
            return await _after_both_captured(call_sid, shipping, billing, ack, messages)

        messages.append({"role": "assistant", "content": ack})
        call_state.save(call_sid, "messages", messages)
        return {"ack": ack, "next_q": "", "next_audio": None, "done": False, "refused": False}

    # ── ASK_REASON ────────────────────────────────────────────────────────────
    if step == "ask_reason":
        try:
            result = await _call_gpt4o(_prompt_ask_reason(shipping, billing), messages)
        except Exception as e:
            logger.error("gpt4o_failed", step=step, error=str(e))
            result = {"response": "I'm sorry, could you repeat that?",
                      "difference_reason": "", "off_topic": False, "refused": False}

        ack     = result.get("response", "")
        refused = bool(result.get("refused", False))
        reason  = (result.get("difference_reason") or "").strip()

        if refused:
            messages.append({"role": "assistant", "content": ack})
            call_state.save(call_sid, "messages", messages)
            return {"ack": ack, "next_q": "", "next_audio": None, "done": True, "refused": True}

        if reason:
            call_state.save(call_sid, "difference_reason", reason)
            call_state.save(call_sid, "step", "done")
            messages.append({"role": "assistant", "content": _CONFIRMATION})
            call_state.save(call_sid, "messages", messages)
            return {"ack": "", "next_q": _CONFIRMATION, "next_audio": "confirmation",
                    "done": True, "refused": False}

        messages.append({"role": "assistant", "content": ack})
        call_state.save(call_sid, "messages", messages)
        return {"ack": ack, "next_q": "", "next_audio": None, "done": False, "refused": False}

    # Fallback (should not happen)
    return {"ack": "", "next_q": _CONFIRMATION, "next_audio": "confirmation",
            "done": True, "refused": False}


async def _after_both_captured(
    call_sid: str, shipping: str, billing: str,
    ack: str, messages: list[dict],
) -> dict:
    """Called when both addresses are in hand. Compares and routes to next step."""
    if _addresses_same(shipping, billing):
        # Same → confirm and close
        call_state.save(call_sid, "step", "done")
        messages.append({"role": "assistant", "content": _CONFIRMATION})
        call_state.save(call_sid, "messages", messages)
        return {"ack": ack, "next_q": _CONFIRMATION, "next_audio": "confirmation",
                "done": True, "refused": False}
    else:
        # Different → ask reason
        call_state.save(call_sid, "step", "ask_reason")
        messages.append({"role": "assistant", "content": ack + " " + _Q_REASON})
        call_state.save(call_sid, "messages", messages)
        return {"ack": ack, "next_q": _Q_REASON, "next_audio": "ask_reason",
                "done": False, "refused": False}


# ── Step 0: Greeting + first question ────────────────────────────────────────

@router.api_route("/verification-call", methods=["GET", "POST"])
async def verification_call_twiml(
    request: Request,
    CallSid: Optional[str] = Form(None),
):
    """
    Entry point. Plays the personalized greeting, then immediately asks
    for the shipping address inside the Gather so the caller's response
    is captured on the first turn.
    """
    base = _base_url(request)
    state = call_state.load(CallSid) if CallSid else {}
    customer_name = state.get("customer_name", "")

    # Greeting text (intro only — question is asked separately)
    if customer_name:
        greeting_text = (
            f"Hi {customer_name}, this is Laundry Owners Warehouse. "
            "We just need to quickly verify your order before we can ship it."
        )
    else:
        greeting_text = (
            "Hello, this is Laundry Owners Warehouse. "
            "We just need to quickly verify your order before we can ship it."
        )

    # Greeting audio: ElevenLabs pre-cached (personalized) > <Say>
    if CallSid and elevenlabs_service.get_personalized_greeting(CallSid):
        greeting_xml = f'<Play>{base}/audio/greeting/{CallSid}</Play>'
    else:
        safe_greeting = greeting_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        greeting_xml = f'<Say voice="alice" language="en-US">{safe_greeting}</Say>'

    # Initialize state
    if CallSid:
        call_state.save(CallSid, "step", "collect_shipping")
        call_state.save(CallSid, "messages", [
            {"role": "assistant", "content": greeting_text + " " + _Q_SHIPPING}
        ])

    # Shipping question plays inside the Gather — caller answers directly
    ask_ship_xml = await _audio(base, _Q_SHIPPING, "ask_shipping")
    body = (
        f"{greeting_xml}\n"
        f"{_gather('/twiml/step/respond', ask_ship_xml, base)}"
    )
    return _xml(body)


# ── Step N: Process response → ack + next question ───────────────────────────

@router.post("/step/respond")
async def step_respond(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
):
    base   = _base_url(request)
    speech = SpeechResult or ""

    result = await _ai_respond(CallSid, speech)

    ack_text   = result["ack"]
    next_q     = result["next_q"]
    next_audio = result["next_audio"]   # ElevenLabs step name or None
    is_done    = result["done"]
    refused    = result["refused"]

    if is_done:
        state     = call_state.load(CallSid)
        shipping  = state.get("shipping_address", "")
        billing   = state.get("billing_address", "")
        reason    = state.get("difference_reason", "")
        approved  = not refused

        asyncio.create_task(_persist_result(CallSid, shipping, billing, reason, approved))
        call_state.clear(CallSid)

        # Build closing audio (ack + confirmation or just confirmation)
        parts = []
        if ack_text:
            parts.append(await _audio(base, ack_text))
        if next_q:
            parts.append(await _audio(base, next_q, next_audio))
        return _xml("\n".join(parts) if parts else
                    f'<Say voice="alice" language="en-US">{_CONFIRMATION}</Say>')

    # Not done — play ack then next question (or just ack if caller went off-topic)
    parts = []
    if ack_text:
        parts.append(await _audio(base, ack_text))

    if next_q:
        # Confirmed a field → play next question inside new Gather
        next_q_xml = await _audio(base, next_q, next_audio)
        gather = _gather("/twiml/step/respond", next_q_xml, base)
        parts.append(gather)
    else:
        # Nothing captured or off-topic — ack already has redirect baked in via GPT-4o
        # Wrap the ack inside a new Gather so we keep listening
        ack_xml = parts.pop() if parts else f'<Say voice="alice" language="en-US">{_Q_SHIPPING}</Say>'
        gather = _gather("/twiml/step/respond", ack_xml, base)
        parts.append(gather)

    return _xml("\n".join(parts))


# ── Background: persist + HubSpot ────────────────────────────────────────────

async def _persist_result(
    call_sid: str,
    shipping: str,
    billing: str,
    diff_reason: str,
    approved: bool,
) -> None:
    fraud_label = "Safe Customer" if approved else "Suspicious"
    risk_score  = 10 if approved else 55
    risk_label  = "low" if approved else "medium"
    summary     = (
        "Customer confirmed addresses. Order approved."
        if approved else
        "Customer did not complete verification. Manual review required."
    )

    lines = []
    if shipping:   lines.append(f"Shipping address: {shipping}")
    if billing:    lines.append(f"Billing address: {billing}")
    if diff_reason: lines.append(f"Reason for different addresses: {diff_reason}")
    transcript = "\n".join(lines) or "(no responses captured)"

    reasons = [
        f"Shipping address provided: {'yes' if shipping else 'no'}",
        f"Billing address provided: {'yes' if billing else 'no'}",
    ]
    if shipping and billing and not _addresses_same(shipping, billing):
        reasons.append(f"Addresses differed — reason provided: {'yes' if diff_reason else 'no'}")

    deal_id: Optional[str] = None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
        call = result.scalar_one_or_none()
        if not call:
            logger.warning("persist_call_not_found", call_sid=call_sid)
            return
        call.transcript      = transcript
        call.risk_score      = risk_score
        call.risk_label      = risk_label
        call.fraud_label     = fraud_label
        call.analysis_summary = summary
        call.reasons         = reasons
        call.raw_claude_json = {
            "shipping_address": shipping,
            "billing_address": billing,
            "difference_reason": diff_reason,
            "approved": approved,
        }
        deal_id = call.hubspot_deal_id
        await db.commit()

    if deal_id:
        try:
            await hubspot_service.update_deal_fraud_status(deal_id, fraud_label)
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Call).where(Call.call_sid == call_sid))
                call = result.scalar_one_or_none()
                if call:
                    call.hubspot_updated = True
                    await db.commit()
        except Exception as e:
            logger.error("hubspot_update_failed", call_sid=call_sid, error=str(e))
    else:
        updated = await hubspot_service.complete_test_order()
        if updated:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Call).where(Call.call_sid == call_sid))
                call = result.scalar_one_or_none()
                if call:
                    call.hubspot_updated = True
                    await db.commit()

    logger.info("verification_complete", call_sid=call_sid,
                approved=approved, risk_score=risk_score, fraud_label=fraud_label)
