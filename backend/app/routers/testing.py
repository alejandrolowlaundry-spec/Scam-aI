"""
Testing endpoint — trigger a verification call to any number.
Used for QA and demo without needing a real HubSpot deal.
"""
import asyncio
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Call
from app.services import twilio_service, hubspot_service, elevenlabs_service, call_state
from app.config import settings
from app.utils.logging import logger

router = APIRouter()


class TestCallRequest(BaseModel):
    phone: str
    email: Optional[str] = None
    order_name: Optional[str] = None


@router.post("/call")
async def initiate_test_call(
    body: TestCallRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    base_url = settings.public_url or str(request.base_url).rstrip("/")
    twiml_url = f"{base_url}/twiml/verification-call"
    status_callback_url = f"{base_url}/webhook/call-status"

    label = body.order_name or body.email or "Test Call"

    call_sid = await twilio_service.make_outbound_call(
        to_number=body.phone,
        twiml_url=twiml_url,
        status_callback_url=status_callback_url,
        hubspot_deal_id=f"TEST-{label[:30]}",
    )

    call = Call(
        call_sid=call_sid,
        hubspot_deal_id=None,
        from_number=settings.twilio_phone_number or "DEMO",
        to_number=body.phone,
        direction="outbound",
        status="initiated",
    )
    db.add(call)
    await db.commit()

    # Look up customer first name by phone for a personalized greeting.
    # Fire pre-generation as a background task so it's ready before the call connects.
    first_name = await hubspot_service.get_contact_first_name_by_phone(body.phone)
    if first_name:
        call_state.save(call_sid, "customer_name", first_name)
        asyncio.create_task(
            elevenlabs_service.generate_personalized_greeting(call_sid, first_name)
        )
        logger.info("personalized_greeting_queued", call_sid=call_sid, name=first_name)

    logger.info("test_call_initiated", call_sid=call_sid, to=body.phone, label=label)

    return {
        "call_sid": call_sid,
        "phone_number": body.phone,
        "message": f"Test call to {body.phone} initiated. Answer your phone!",
    }
