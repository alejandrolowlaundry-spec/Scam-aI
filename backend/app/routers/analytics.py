from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from collections import Counter

from app.database import get_db
from app.models import Call
from app.schemas import AnalyticsSummary, DailyCount, TopSignal

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    calls = (await db.execute(select(Call).where(Call.risk_score.isnot(None)))).scalars().all()

    total = len(calls)
    safe = sum(1 for c in calls if c.fraud_label == "Safe Customer")
    suspicious = sum(1 for c in calls if c.fraud_label == "Suspicious")
    scams = sum(1 for c in calls if c.fraud_label == "Confirmed Scam")
    avg_score = round(sum(c.risk_score for c in calls) / total, 1) if total else 0.0

    # Calls by day (last 30 days)
    from datetime import datetime, timedelta
    day_buckets: dict[str, dict] = {}
    for c in calls:
        day = c.created_at.strftime("%Y-%m-%d")
        if day not in day_buckets:
            day_buckets[day] = {"total": 0, "high": 0, "medium": 0, "low": 0}
        day_buckets[day]["total"] += 1
        if c.risk_label:
            day_buckets[day][c.risk_label] += 1

    calls_by_day = [
        DailyCount(date=d, **v)
        for d, v in sorted(day_buckets.items())[-30:]
    ]

    # Top signals across all calls
    keyword_counter: Counter = Counter()
    for c in calls:
        if c.signals:
            for kw in c.signals.get("keywords", []):
                keyword_counter[kw] += 1
            for pt in c.signals.get("pressure_tactics", []):
                keyword_counter[pt] += 1
            for sm in c.signals.get("script_match", []):
                keyword_counter[sm] += 1

    top_signals = [
        TopSignal(signal=sig, count=cnt)
        for sig, cnt in keyword_counter.most_common(10)
    ]

    return AnalyticsSummary(
        total_calls=total,
        safe_customers=safe,
        suspicious=suspicious,
        confirmed_scams=scams,
        avg_risk_score=avg_score,
        calls_by_day=calls_by_day,
        top_signals=top_signals,
    )
