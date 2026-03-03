"""
HubSpot integration endpoints.

GET  /hubspot/deals               — fetch pending fraud deals
POST /hubspot/initiate-call/{id}  — dial the customer and create a call record
GET  /hubspot/deals/{id}          — fetch single deal detail
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Call
from app.schemas import HubSpotDealsOut, InitiateCallOut
from app.services import hubspot_service, twilio_service
from app.config import settings
from app.utils.logging import logger
from fastapi import Request

router = APIRouter()


@router.get("/deals", response_model=HubSpotDealsOut)
async def list_pending_deals():
    deals = await hubspot_service.get_pending_fraud_deals()
    return HubSpotDealsOut(total=len(deals), deals=deals)


@router.post("/initiate-call/{deal_id}", response_model=InitiateCallOut)
async def initiate_call(
    deal_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Fetch deal from HubSpot
    deal = await hubspot_service.get_deal_by_id(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found in HubSpot")

    if not deal.contact_phone:
        raise HTTPException(
            status_code=422,
            detail=f"Deal {deal_id} has no phone number on associated contact",
        )

    # Use PUBLIC_URL when set (required for Twilio to reach local server via tunnel)
    base_url = settings.public_url or str(request.base_url).rstrip("/")
    twiml_url = f"{base_url}/twiml/verification-call"
    status_callback_url = f"{base_url}/webhook/call-status"

    # Make Twilio call
    call_sid = await twilio_service.make_outbound_call(
        to_number=deal.contact_phone,
        twiml_url=twiml_url,
        status_callback_url=status_callback_url,
        hubspot_deal_id=deal_id,
    )

    # Persist call record
    call = Call(
        call_sid=call_sid,
        hubspot_deal_id=deal_id,
        hubspot_contact_id=deal.contact_id,
        from_number=settings.twilio_phone_number or "DEMO",
        to_number=deal.contact_phone,
        direction="outbound",
        status="initiated",
    )
    db.add(call)
    await db.commit()

    logger.info(
        "call_initiated_from_hubspot",
        deal_id=deal_id,
        call_sid=call_sid,
        to=deal.contact_phone,
    )

    return InitiateCallOut(
        call_sid=call_sid,
        deal_id=deal_id,
        phone_number=deal.contact_phone,
        message=f"Outbound verification call initiated to {deal.contact_phone}",
    )


@router.get("/deals/{deal_id}")
async def get_deal(deal_id: str):
    deal = await hubspot_service.get_deal_by_id(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal
