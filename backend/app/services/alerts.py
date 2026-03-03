"""
Alert service — sends email (SendGrid) + SMS (Twilio) for high-risk calls.
"""
from __future__ import annotations
import httpx
from typing import Optional
from app.config import settings
from app.utils.logging import logger


async def send_high_risk_alert(
    call_sid: str,
    risk_score: int,
    fraud_label: str,
    from_number: str,
    to_number: str,
    reasons: list[str],
    hubspot_deal_id: Optional[str] = None,
) -> None:
    """Fire-and-forget alerts. Errors are logged but not raised."""
    tasks = []
    if settings.sendgrid_api_key and settings.alert_to_email:
        tasks.append(_send_email(call_sid, risk_score, fraud_label, from_number, reasons, hubspot_deal_id))
    if settings.twilio_account_sid and settings.alert_to_phone:
        tasks.append(_send_sms(call_sid, risk_score, fraud_label, from_number))

    import asyncio
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _send_email(
    call_sid: str,
    risk_score: int,
    fraud_label: str,
    from_number: str,
    reasons: list[str],
    hubspot_deal_id: str | None,
) -> None:
    reasons_html = "".join(f"<li>{r}</li>" for r in reasons)
    deal_info = f"<p><strong>HubSpot Deal:</strong> {hubspot_deal_id}</p>" if hubspot_deal_id else ""

    body = {
        "personalizations": [{"to": [{"email": settings.alert_to_email}]}],
        "from": {"email": settings.alert_from_email},
        "subject": f"🚨 HIGH RISK CALL DETECTED — Score {risk_score}/100",
        "content": [
            {
                "type": "text/html",
                "value": f"""
<h2 style="color:red">⚠️ Fraud Alert: {fraud_label}</h2>
<p><strong>Call SID:</strong> {call_sid}</p>
<p><strong>From:</strong> {from_number}</p>
<p><strong>Risk Score:</strong> {risk_score}/100</p>
{deal_info}
<h3>Top Reasons:</h3>
<ul>{reasons_html}</ul>
<p>Review in dashboard: {settings.frontend_url}/calls/{call_sid}</p>
""",
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
                json=body,
            )
            resp.raise_for_status()
            logger.info("alert_email_sent", call_sid=call_sid, to=settings.alert_to_email)
    except Exception as e:
        logger.error("alert_email_failed", call_sid=call_sid, error=str(e))


async def _send_sms(
    call_sid: str,
    risk_score: int,
    fraud_label: str,
    from_number: str,
) -> None:
    if settings.demo_mode:
        logger.info("demo_sms_alert", call_sid=call_sid, score=risk_score)
        return

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            to=settings.alert_to_phone,
            from_=settings.twilio_phone_number,
            body=(
                f"🚨 FRAUD ALERT [{fraud_label}] "
                f"Score: {risk_score}/100 | "
                f"From: {from_number} | "
                f"SID: {call_sid}"
            ),
        )
        logger.info("alert_sms_sent", call_sid=call_sid, to=settings.alert_to_phone)
    except Exception as e:
        logger.error("alert_sms_failed", call_sid=call_sid, error=str(e))
