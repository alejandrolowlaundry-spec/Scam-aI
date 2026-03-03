from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.database import get_db
from app.models import Call
from app.schemas import CallOut, CallListOut

router = APIRouter()


@router.get("", response_model=CallListOut)
async def list_calls(
    db: AsyncSession = Depends(get_db),
    risk_label: Optional[str] = Query(None, description="Filter: low | medium | high"),
    fraud_label: Optional[str] = Query(None, description="Filter: Safe Customer | Suspicious | Confirmed Scam"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Call).order_by(desc(Call.created_at))
    count_query = select(func.count()).select_from(Call)

    if risk_label:
        query = query.where(Call.risk_label == risk_label)
        count_query = count_query.where(Call.risk_label == risk_label)
    if fraud_label:
        query = query.where(Call.fraud_label == fraud_label)
        count_query = count_query.where(Call.fraud_label == fraud_label)

    total = (await db.execute(count_query)).scalar_one()
    calls = (await db.execute(query.offset(offset).limit(limit))).scalars().all()

    return CallListOut(total=total, calls=calls)


@router.get("/{call_sid}", response_model=CallOut)
async def get_call(call_sid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Call).where(Call.call_sid == call_sid))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
