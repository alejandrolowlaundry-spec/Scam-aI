"""
Twilio webhook handlers.

Twilio fires these automatically:
  POST /webhook/call-status     — when call state changes (initiated → completed)
  POST /webhook/recording-complete — when a recording is ready

Full pipeline: call-status (completed) → recording-complete → transcribe → analyze → update HubSpot
"""
import asyncio
from fastapi import APIRouter, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from typing import Optional

from app.database import AsyncSessionLocal
from app.models import Call
from app.services import (
    twilio_service,
    transcription,
    claude_analysis,
    risk_scoring,
    alerts,
    hubspot_service,
)
from app.utils.logging import logger

router = APIRouter()


async def _process_call(call_sid: str, recording_url: str) -> None:
    """Background task: transcribe → analyze → persist → update HubSpot → alert."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
        call = result.scalar_one_or_none()
        if not call:
            logger.warning("call_not_found_for_processing", call_sid=call_sid)
            return

        # 1. Transcribe (fall back to existing transcript if AssemblyAI fails)
        try:
            transcript = await transcription.transcribe_recording(recording_url, call_sid)
            call.transcript = transcript
            await db.commit()
        except Exception as e:
            logger.warning("transcription_failed_using_fallback", call_sid=call_sid, error=str(e))
            transcript = call.transcript
            if not transcript:
                logger.error("no_transcript_available", call_sid=call_sid)
                return

        # 2. Analyze with Claude
        try:
            analysis = await claude_analysis.analyze_transcript(
                transcript=transcript,
                direction=call.direction,
                from_number=call.from_number,
                to_number=call.to_number,
                duration=call.duration or 0,
            )
        except Exception as e:
            logger.error("analysis_failed", call_sid=call_sid, error=str(e))
            return

        # 3. Persist results
        call.risk_score = analysis.risk_score
        call.risk_label = analysis.risk_label
        call.fraud_label = analysis.fraud_label
        call.reasons = analysis.reasons
        call.signals = analysis.signals.model_dump()
        call.raw_claude_json = analysis.model_dump()
        call.analysis_summary = analysis.summary

        # 4. Update HubSpot deal status + attach call note
        if call.hubspot_deal_id:
            updated = await hubspot_service.update_deal_fraud_status(
                call.hubspot_deal_id, analysis.fraud_label
            )
            call.hubspot_updated = updated

            # Attach full fraud analysis as a note on the deal
            await hubspot_service.create_call_note(
                deal_id=call.hubspot_deal_id,
                call_sid=call_sid,
                fraud_label=analysis.fraud_label,
                risk_score=analysis.risk_score,
                reasons=analysis.reasons,
                transcript=call.transcript,
                recording_url=call.recording_url,
            )

        # 5. Alert if high risk
        if analysis.risk_label == "high" and not call.alert_sent:
            await alerts.send_high_risk_alert(
                call_sid=call_sid,
                risk_score=analysis.risk_score,
                fraud_label=analysis.fraud_label,
                from_number=call.from_number,
                to_number=call.to_number,
                reasons=analysis.reasons,
                hubspot_deal_id=call.hubspot_deal_id,
            )
            call.alert_sent = True

        await db.commit()
        logger.info(
            "call_processing_complete",
            call_sid=call_sid,
            risk_score=analysis.risk_score,
            fraud_label=analysis.fraud_label,
        )


@router.post("/call-status")
async def call_status_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Duration: Optional[str] = Form(None),
    RecordingUrl: Optional[str] = Form(None),
    RecordingSid: Optional[str] = Form(None),
):
    # Verify Twilio signature
    sig = request.headers.get("X-Twilio-Signature", "")
    params = dict(await request.form())
    if not twilio_service.verify_twilio_signature(str(request.url), params, sig):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    logger.info("call_status_webhook", call_sid=CallSid, status=CallStatus)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()

        if not call:
            # Inbound call — create record
            call = Call(
                call_sid=CallSid,
                from_number=From or "unknown",
                to_number=To or "unknown",
                direction="inbound",
                status=CallStatus,
            )
            db.add(call)
        else:
            call.status = CallStatus
            if Duration:
                call.duration = int(Duration)

        await db.commit()

    return Response(content="<?xml version='1.0'?><Response/>", media_type="application/xml")


@router.post("/recording-complete")
async def recording_complete_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    RecordingSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: Optional[str] = Form(None),
    RecordingStatus: Optional[str] = Form(None),
):
    sig = request.headers.get("X-Twilio-Signature", "")
    params = dict(await request.form())
    if not twilio_service.verify_twilio_signature(str(request.url), params, sig):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    logger.info(
        "recording_complete_webhook",
        call_sid=CallSid,
        recording_sid=RecordingSid,
        status=RecordingStatus,
    )

    if RecordingStatus and RecordingStatus != "completed":
        return Response(content="<?xml version='1.0'?><Response/>", media_type="application/xml")

    # Build authenticated recording URL (MP3)
    full_url = twilio_service.get_recording_url(RecordingSid)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.call_sid == CallSid))
        call = result.scalar_one_or_none()
        if call:
            call.recording_url = full_url
            call.recording_sid = RecordingSid
            if RecordingDuration:
                call.duration = int(RecordingDuration)
            await db.commit()

    # Kick off analysis pipeline in background
    background_tasks.add_task(_process_call, CallSid, full_url)

    return Response(content="<?xml version='1.0'?><Response/>", media_type="application/xml")
