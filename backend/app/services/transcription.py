"""
Transcription pipeline.

Strategy (in priority order):
  1. AssemblyAI — best quality, async, if ASSEMBLYAI_API_KEY is set
  2. Demo mode   — returns mock transcript
  3. Fallback    — returns placeholder so analysis can still run

Upgrade path to streaming:
  Replace AssemblyAI polling with AssemblyAI real-time WebSocket OR
  integrate Deepgram streaming via Twilio Media Streams webhook.
"""
import httpx
import asyncio
from app.config import settings
from app.utils.logging import logger

DEMO_TRANSCRIPT = """
Agent: Hello, this is the account verification team calling. May I speak with the account holder?
Customer: Yes, this is them. What's this about?
Agent: We need to verify some account details for security purposes. Can you confirm your name and the last 4 digits of your account?
Customer: Sure, my name is John Smith and the last 4 are 4521.
Agent: Thank you, Mr. Smith. Can you confirm your address on file?
Customer: It's 123 Main Street, Springfield.
Agent: Great. And can you confirm the nature of your recent transaction for $450?
Customer: Yes, that was a purchase I made online for electronics last Tuesday.
Agent: Perfect, everything checks out. Thank you for your cooperation. Have a great day.
Customer: Thank you, goodbye.
"""

DEMO_SCAM_TRANSCRIPT = """
Caller: Hello, I am calling from the Internal Revenue Service. This is an urgent legal matter.
Customer: What? IRS? What is this about?
Caller: You owe $4,500 in back taxes and if you do not pay immediately you will be arrested today.
Customer: That doesn't sound right. Can I call you back?
Caller: No! You cannot hang up. This is an active arrest warrant. You must act now.
Caller: You need to go to Walmart and buy Google Play gift cards. Do not tell anyone.
Customer: I should call my accountant—
Caller: If you hang up you will be arrested within the hour. This is your last chance.
"""


async def transcribe_recording(recording_url: str, call_sid: str) -> str:
    if settings.demo_mode:
        if "scam" in call_sid.lower():
            return DEMO_SCAM_TRANSCRIPT.strip()
        return DEMO_TRANSCRIPT.strip()

    if settings.assemblyai_api_key:
        return await _transcribe_assemblyai(recording_url, call_sid)

    logger.warning("no_transcription_provider", call_sid=call_sid)
    return "(Transcription unavailable — set ASSEMBLYAI_API_KEY)"


async def _transcribe_assemblyai(recording_url: str, call_sid: str) -> str:
    headers = {"authorization": settings.assemblyai_api_key}

    async with httpx.AsyncClient(timeout=120) as client:
        # Submit job
        resp = await client.post(
            "https://api.assemblyai.com/v2/transcript",
            json={"audio_url": recording_url},
            headers=headers,
        )
        resp.raise_for_status()
        transcript_id = resp.json()["id"]
        logger.info("assemblyai_job_submitted", transcript_id=transcript_id, call_sid=call_sid)

        # Poll for completion (max 3 min)
        for attempt in range(36):
            await asyncio.sleep(5)
            poll = await client.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers,
            )
            poll.raise_for_status()
            data = poll.json()

            if data["status"] == "completed":
                logger.info("assemblyai_transcription_complete", call_sid=call_sid)
                return data.get("text", "")
            elif data["status"] == "error":
                raise RuntimeError(f"AssemblyAI error: {data.get('error')}")

        raise TimeoutError("AssemblyAI transcription timed out after 3 minutes")
