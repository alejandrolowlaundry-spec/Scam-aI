"""
ElevenLabs Text-to-Speech service.

Generates one audio clip per call step and caches each separately.
Cache key: "{voice_id}:{step_name}"
"""
from __future__ import annotations
import httpx
from typing import Optional
from app.config import settings
from app.utils.logging import logger

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# ── Per-step scripts — conversational, natural pacing ─────────────────────────
#
# Ellipses (…) create a natural breath pause in ElevenLabs.
# Short sentences keep the flow light and phone-friendly.

STEP_SCRIPTS: dict[str, str] = {
    "ask_shipping": (
        "Could you please confirm the shipping address for the order?"
    ),
    "ask_billing": (
        "Thank you. Could you also confirm the billing address used for the payment?"
    ),
    "ask_reason": (
        "I noticed the shipping and billing addresses are different. "
        "Could you briefly let me know why?"
    ),
    "confirmation": (
        "Perfect, thank you for confirming. "
        "Your order verification is complete and your order will proceed to shipping."
    ),
}

# ── Cache: { "{voice_id}:{step}" : mp3_bytes } ────────────────────────────────

_audio_cache: dict[str, bytes] = {}


async def generate_audio(text: str, voice_id: str | None = None) -> bytes:
    """Generate speech via ElevenLabs and return MP3 bytes (no caching)."""
    vid = voice_id or settings.elevenlabs_voice_id

    if settings.demo_mode or not settings.elevenlabs_api_key:
        return _silent_mp3()

    url = ELEVENLABS_TTS_URL.format(voice_id=vid)
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {
            "stability": 0.40,        # lower = more natural variation, less robotic
            "similarity_boost": 0.75,  # keeps Rachel's character consistent
            "style": 0.20,             # adds expressive, conversational inflection
            "use_speaker_boost": True, # sharpens clarity on phone audio
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.content


async def get_step_audio(step: str) -> bytes:
    """Return ElevenLabs audio for a named call step, cached after first generation."""
    text = STEP_SCRIPTS.get(step)
    if not text:
        raise ValueError(f"Unknown step: {step!r}")

    if settings.demo_mode or not settings.elevenlabs_api_key:
        return _silent_mp3()

    vid = settings.elevenlabs_voice_id
    cache_key = f"{vid}:{step}"

    if cache_key in _audio_cache:
        logger.info("elevenlabs_step_cache_hit", step=step)
        return _audio_cache[cache_key]

    audio = await generate_audio(text, vid)
    _audio_cache[cache_key] = audio
    logger.info("elevenlabs_step_audio_cached", step=step, bytes=len(audio))
    return audio


# ── Per-call personalized greeting cache: { call_sid: mp3_bytes } ─────────────

_greeting_cache: dict[str, bytes] = {}


async def generate_personalized_greeting(call_sid: str, customer_name: str) -> None:
    """
    Pre-generate a personalized greeting for a specific call using ElevenLabs
    and cache it by call_sid. Called as a background task before the call connects
    so there is zero audio latency when Twilio fetches the TwiML.
    """
    text = (
        f"Hi {customer_name}… this is Laundry Owners Warehouse. "
        "We just need to quickly verify your order before we can ship it."
    )
    try:
        audio = await generate_audio(text)
        _greeting_cache[call_sid] = audio
        logger.info("personalized_greeting_cached", call_sid=call_sid, name=customer_name)
    except Exception as e:
        logger.warning("personalized_greeting_failed", call_sid=call_sid, error=str(e))


def get_personalized_greeting(call_sid: str) -> Optional[bytes]:
    return _greeting_cache.get(call_sid)


def clear_personalized_greeting(call_sid: str) -> None:
    _greeting_cache.pop(call_sid, None)


# ── Per-response dynamic audio cache: { uuid_key: mp3_bytes } ────────────────

_dynamic_cache: dict[str, bytes] = {}


async def cache_dynamic_audio(key: str, text: str) -> bool:
    """Generate ElevenLabs audio for dynamic text and cache by key. Returns True on success."""
    try:
        audio = await generate_audio(text)
        _dynamic_cache[key] = audio
        logger.info("dynamic_audio_cached", key=key, chars=len(text))
        return True
    except Exception as e:
        logger.warning("dynamic_audio_failed", key=key, error=str(e))
        return False


def get_dynamic_audio(key: str) -> Optional[bytes]:
    return _dynamic_cache.get(key)


def invalidate_cache() -> None:
    """Force regeneration of all cached audio on next request."""
    _audio_cache.clear()
    _greeting_cache.clear()
    _dynamic_cache.clear()


def _silent_mp3() -> bytes:
    """Minimal valid MP3 frame — keeps Twilio happy in demo mode."""
    return bytes([
        0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
    ])
