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

        # 4. Update HubSpot deal status + attach call note + update contact name
        if call.hubspot_deal_id:
            # Resolve to numeric deal ID (handles text entries like "12345 Name Pending")
            real_deal_id = await hubspot_service.resolve_deal_id(call.hubspot_deal_id)
            if real_deal_id and real_deal_id != call.hubspot_deal_id:
                call.hubspot_deal_id = real_deal_id
                await db.commit()

            if real_deal_id:
                updated = await hubspot_service.update_deal_fraud_status(
                    real_deal_id, analysis.fraud_label
                )
                call.hubspot_updated = updated
            else:
                updated = False

            # Update contact name if we have a contact ID and a name on record
            if real_deal_id and call.hubspot_contact_id:
                deal = await hubspot_service.get_deal_by_id(real_deal_id)
                if deal and deal.contact_name:
                    parts = deal.contact_name.split(" ", 1)
                    firstname = parts[0]
                    lastname  = parts[1] if len(parts) > 1 else ""
                    await hubspot_service.update_contact_name(
                        call.hubspot_contact_id, firstname, lastname
                    )

            # Attach full fraud analysis as a note on the deal
            if real_deal_id:
                await hubspot_service.create_call_note(
                    deal_id=real_deal_id,
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


async def _hubspot_update_on_completion(call_sid: str) -> None:
    """Fire HubSpot update when call completes — uses fraud_label from TwiML if available, else 'Safe Customer'."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.call_sid == call_sid))
        call = result.scalar_one_or_none()
        if not call or not call.hubspot_deal_id or call.hubspot_updated:
            return

        fraud_label = call.fraud_label or "Safe Customer"

        real_deal_id = await hubspot_service.resolve_deal_id(call.hubspot_deal_id)
        if not real_deal_id:
            logger.warning("hubspot_update_on_completion_no_deal", call_sid=call_sid)
            return

        if real_deal_id != call.hubspot_deal_id:
            call.hubspot_deal_id = real_deal_id

        updated = await hubspot_service.update_deal_fraud_status(real_deal_id, fraud_label)
        call.hubspot_updated = updated

        # Update contact name
        deal = await hubspot_service.get_deal_by_id(real_deal_id)
        if deal and deal.contact_id and deal.contact_name:
            parts = deal.contact_name.split(" ", 1)
            await hubspot_service.update_contact_name(
                deal.contact_id, parts[0], parts[1] if len(parts) > 1 else ""
            )

        await db.commit()
        logger.info("hubspot_updated_on_call_completion", call_sid=call_sid,
                    deal_id=real_deal_id, fraud_label=fraud_label)


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

    # As soon as call is answered, update HubSpot immediately
    if CallStatus == "in-progress":
        background_tasks.add_task(_hubspot_update_on_completion, CallSid)

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
