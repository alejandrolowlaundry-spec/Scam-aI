"""
Audio streaming endpoints.

Twilio's <Play> tag fetches audio from a URL.
Each call step has its own endpoint so ElevenLabs audio is cached per step.
"""
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.elevenlabs_service import (
    get_step_audio, generate_audio, get_personalized_greeting, get_dynamic_audio,
)
from app.utils.logging import logger

router = APIRouter()


@router.get("/step/{step_name}")
async def serve_step_audio(step_name: str):
    """
    Stream ElevenLabs audio for a specific call step.
    Used inside <Play> within <Gather> in the TwiML flow.

    Steps: greeting, ask_order, ask_shipping, ask_billing, approved, manual_review
    """
    try:
        audio = await get_step_audio(step_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown step: {step_name!r}")

    logger.info("audio_step_served", step=step_name, bytes=len(audio))
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(audio)),
        },
    )


@router.get("/greeting/{call_sid}")
async def serve_personalized_greeting(call_sid: str):
    """
    Stream the pre-generated ElevenLabs personalized greeting for a specific call.
    Generated before the call connects — zero latency when Twilio fetches it.
    """
    audio = get_personalized_greeting(call_sid)
    if not audio:
        raise HTTPException(status_code=404, detail="Greeting not ready for this call")
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Length": str(len(audio)),
        },
    )


@router.get("/dynamic/{key}")
async def serve_dynamic_audio(key: str):
    """
    Stream a dynamically generated ElevenLabs audio clip cached by UUID key.
    Used by <Play> tags in the GPT-4o-driven conversational TwiML flow.
    """
    audio = get_dynamic_audio(key)
    if not audio:
        raise HTTPException(status_code=404, detail="Dynamic audio not found")
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Length": str(len(audio)),
        },
    )


@router.get("/custom")
async def serve_custom_audio(text: str):
    """
    Generate and stream a one-off ElevenLabs audio clip.
    Example: GET /audio/custom?text=Hello+John
    """
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="Text too long (max 500 chars)")
    audio = await generate_audio(text)
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")
