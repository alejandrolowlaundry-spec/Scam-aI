import hmac
import hashlib
import base64
from urllib.parse import urlencode, urlparse, parse_qsl
from twilio.rest import Client
from app.config import settings
from app.utils.logging import logger


def get_twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def verify_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Validate that a webhook request genuinely came from Twilio."""
    if settings.demo_mode:
        return True

    auth_token = settings.twilio_auth_token
    s = url
    if params:
        s += "".join(f"{k}{v}" for k, v in sorted(params.items()))

    mac = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    expected = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(expected, signature)


async def make_outbound_call(
    to_number: str,
    twiml_url: str,
    status_callback_url: str,
    hubspot_deal_id: str = "",
) -> str:
    """Initiate an outbound call. Returns call SID."""
    if settings.demo_mode:
        import uuid
        fake_sid = f"DEMO-{uuid.uuid4().hex[:16].upper()}"
        logger.info(
            "demo_outbound_call",
            to=to_number,
            deal_id=hubspot_deal_id,
            call_sid=fake_sid,
        )
        return fake_sid

    client = get_twilio_client()
    call = client.calls.create(
        to=to_number,
        from_=settings.twilio_phone_number,
        url=twiml_url,
        status_callback=status_callback_url,
        status_callback_method="POST",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        record=True,
        recording_status_callback=status_callback_url.replace(
            "/webhook/call-status", "/webhook/recording-complete"
        ),
    )
    logger.info("outbound_call_initiated", call_sid=call.sid, to=to_number)
    return call.sid


def get_recording_url(recording_sid: str) -> str:
    """Return the authenticated MP3 URL for a Twilio recording."""
    return (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.twilio_account_sid}/Recordings/{recording_sid}.mp3"
    )
