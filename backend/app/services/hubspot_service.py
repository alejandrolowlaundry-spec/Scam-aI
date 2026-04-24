"""
HubSpot CRM integration using API v3.

Deal name tag convention (already in your HubSpot):
  (Fraud Check = Pending Verification)  ← fetch these, call them
  (Fraud Check = Approved)              ← safe customer result
  (Fraud Check = Confirmed Fraud)       ← confirmed scam result

After a call we RENAME the deal by replacing the tag in the deal name.
No custom properties needed — everything lives in the deal name.
"""
from __future__ import annotations
import re
import httpx
from typing import Optional
from app.config import settings
from app.schemas import HubSpotDeal
from app.utils.logging import logger

BASE_URL = "https://api.hubapi.com"

# Tags as they appear in deal names
TAG_PENDING   = "(Fraud Check = Pending Verification)"
TAG_APPROVED  = "(Fraud Check = Approved)"
TAG_FRAUD     = "(Fraud Check = Confirmed Fraud)"
TAG_REVIEW    = "(Fraud Check = Needs Review)"   # for Suspicious verdict

# Map fraud_label → deal name tag
FRAUD_LABEL_TO_TAG = {
    "Safe Customer":    TAG_APPROVED,
    "Suspicious":       TAG_REVIEW,
    "Confirmed Scam":   TAG_FRAUD,
}

# Map fraud_label → deal stage ID (pulled from config at runtime)
def _fraud_label_to_stage_id(fraud_label: str) -> str:
    mapping = {
        "Safe Customer":  settings.hubspot_stage_safe_customer,
        "Suspicious":     settings.hubspot_stage_review,
        "Confirmed Scam": settings.hubspot_stage_fraud,
    }
    return mapping.get(fraud_label, "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.effective_hubspot_token}",
        "Content-Type": "application/json",
    }


def _replace_tag(deal_name: str, new_tag: str) -> str:
    """Swap any existing Fraud Check tag in the deal name with the new one."""
    cleaned = re.sub(r"\s*\(Fraud Check = [^)]+\)", "", deal_name).strip()
    return f"{cleaned} {new_tag}"


async def resolve_deal_id(deal_id_or_hint: str) -> Optional[str]:
    """
    If deal_id_or_hint is already numeric, return it as-is.
    Otherwise search HubSpot by matching ALL words in the deal name.
    """
    if deal_id_or_hint.strip().isdigit():
        return deal_id_or_hint.strip()

    words = [w for w in deal_id_or_hint.strip().split() if w]
    filters = [
        {"propertyName": "dealname", "operator": "CONTAINS_TOKEN", "value": w}
        for w in words
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/crm/v3/objects/deals/search",
                headers=_headers(),
                json={
                    "filterGroups": [{"filters": filters}],
                    "properties": ["dealname"],
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                found_id = results[0]["id"]
                logger.info("deal_id_resolved", hint=deal_id_or_hint, resolved_id=found_id)
                return found_id
        except Exception as e:
            logger.warning("resolve_deal_id_failed", hint=deal_id_or_hint, error=str(e))

    return None


async def update_deal_stage(deal_id: str, stage_id: str) -> bool:
    """Update the HubSpot deal stage property (dealstage)."""
    if not stage_id:
        logger.info("hubspot_stage_update_skipped", deal_id=deal_id,
                    reason="No stage ID configured for this fraud label")
        return False

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.patch(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}",
                headers=_headers(),
                json={"properties": {"dealstage": stage_id}},
            )
            resp.raise_for_status()
            logger.info("hubspot_deal_stage_updated", deal_id=deal_id, stage_id=stage_id)
            return True
        except Exception as e:
            logger.error("hubspot_stage_update_failed", deal_id=deal_id,
                         stage_id=stage_id, error=str(e))
            return False


async def update_contact_name(contact_id: str, firstname: str, lastname: str = "") -> bool:
    """Write firstname (and optionally lastname) back to the HubSpot contact record."""
    if not contact_id or not firstname:
        return False

    props: dict = {"firstname": firstname}
    if lastname:
        props["lastname"] = lastname

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.patch(
                f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                headers=_headers(),
                json={"properties": props},
            )
            resp.raise_for_status()
            logger.info("hubspot_contact_name_updated", contact_id=contact_id,
                        firstname=firstname, lastname=lastname)
            return True
        except Exception as e:
            logger.error("hubspot_contact_name_update_failed", contact_id=contact_id,
                         error=str(e))
            return False


async def get_pending_fraud_deals() -> list[HubSpotDeal]:
    """Fetch deals whose name contains '(Fraud Check = Pending Verification)'."""
    if settings.demo_mode:
        return _demo_deals()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/crm/v3/objects/deals/search",
            headers=_headers(),
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "dealname",
                        "operator": "CONTAINS_TOKEN",
                        "value": "Pending",
                    }]
                }],
                "properties": ["dealname", "amount", "createdate"],
                "limit": 100,
            },
        )
        resp.raise_for_status()
        raw_deals = resp.json().get("results", [])

    deals: list[HubSpotDeal] = []
    for raw in raw_deals:
        props = raw.get("properties", {})
        deal_id = raw["id"]
        contact = await _get_deal_contact(deal_id)

        deals.append(HubSpotDeal(
            deal_id=deal_id,
            deal_name=props.get("dealname", "Unnamed Deal"),
            fraud_status=TAG_PENDING,
            amount=props.get("amount"),
            created_at=props.get("createdate"),
            contact_id=contact.get("id"),
            contact_name=contact.get("name"),
            contact_email=contact.get("email"),
            contact_phone=contact.get("phone"),
        ))

    logger.info("hubspot_deals_fetched", count=len(deals))
    return deals


async def _get_deal_contact(deal_id: str) -> dict:
    """Get the first associated contact for a deal."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}/associations/contacts",
                headers=_headers(),
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return {}
            contact_id = results[0]["id"]

            contact_resp = await client.get(
                f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                headers=_headers(),
                params={"properties": "firstname,lastname,email,phone,mobilephone"},
            )
            contact_resp.raise_for_status()
            props = contact_resp.json().get("properties", {})
            first = props.get("firstname", "")
            last = props.get("lastname", "")
            return {
                "id": contact_id,
                "name": f"{first} {last}".strip() or None,
                "email": props.get("email"),
                "phone": props.get("phone") or props.get("mobilephone"),
            }
        except Exception as e:
            logger.warning("hubspot_contact_fetch_failed", deal_id=deal_id, error=str(e))
            return {}


async def update_deal_fraud_status(deal_id: str, fraud_label: str) -> bool:
    """
    Update the deal after a fraud verification call:
      1. Rename deal — replaces the Fraud Check tag in the deal name
      2. Update dealstage — moves deal to the configured pipeline stage
    fraud_label: 'Safe Customer' | 'Suspicious' | 'Confirmed Scam'
    """
    if settings.demo_mode:
        logger.info("demo_hubspot_update", deal_id=deal_id, fraud_label=fraud_label)
        return True

    new_tag   = FRAUD_LABEL_TO_TAG.get(fraud_label, TAG_REVIEW)
    stage_id  = _fraud_label_to_stage_id(fraud_label)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # 1. Fetch current deal name
            get_resp = await client.get(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}",
                headers=_headers(),
                params={"properties": "dealname"},
            )
            get_resp.raise_for_status()
            current_name = get_resp.json()["properties"].get("dealname", "")

            new_name = _replace_tag(current_name, new_tag)

            # 2. Build the PATCH payload — always update name, add stage if configured
            patch_props: dict = {"dealname": new_name}
            if stage_id:
                patch_props["dealstage"] = stage_id

            patch_resp = await client.patch(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}",
                headers=_headers(),
                json={"properties": patch_props},
            )
            patch_resp.raise_for_status()
            logger.info("hubspot_deal_updated", deal_id=deal_id,
                        new_name=new_name, stage_id=stage_id or "not_configured")
            return True
        except Exception as e:
            logger.error("hubspot_update_failed", deal_id=deal_id, error=str(e))
            return False


async def get_deal_by_id(deal_id: str) -> Optional[HubSpotDeal]:
    if settings.demo_mode:
        return _demo_deals()[0]

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}",
                headers=_headers(),
                params={"properties": "dealname,amount,createdate"},
            )
            resp.raise_for_status()
            raw = resp.json()
            props = raw.get("properties", {})
            contact = await _get_deal_contact(deal_id)
            deal_name = props.get("dealname", "")
            return HubSpotDeal(
                deal_id=deal_id,
                deal_name=deal_name,
                fraud_status=TAG_PENDING,
                amount=props.get("amount"),
                created_at=props.get("createdate"),
                contact_id=contact.get("id"),
                contact_name=contact.get("name"),
                contact_email=contact.get("email"),
                contact_phone=contact.get("phone"),
            )
        except Exception as e:
            logger.error("hubspot_get_deal_failed", deal_id=deal_id, error=str(e))
            return None


async def create_call_note(
    deal_id: str,
    call_sid: str,
    fraud_label: str,
    risk_score: int,
    reasons: list[str],
    transcript: str | None,
    recording_url: str | None,
) -> bool:
    """Attach a fraud analysis note to the deal inside HubSpot."""
    if settings.demo_mode:
        logger.info("demo_hubspot_note", deal_id=deal_id, fraud_label=fraud_label)
        return True

    reasons_text = "\n".join(f"  • {r}" for r in reasons)
    transcript_snippet = (transcript or "")[:800] + ("…" if transcript and len(transcript) > 800 else "")
    recording_line = f"\nRecording: {recording_url}" if recording_url else ""

    note_body = (
        f"Fraud Verification Call Result\n"
        f"{'─' * 40}\n"
        f"Call SID:    {call_sid}\n"
        f"Verdict:     {fraud_label}\n"
        f"Risk Score:  {risk_score}/100\n"
        f"{recording_line}\n\n"
        f"Top Reasons:\n{reasons_text}\n\n"
        f"Transcript (excerpt):\n{transcript_snippet}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            note_resp = await client.post(
                f"{BASE_URL}/crm/v3/objects/notes",
                headers=_headers(),
                json={
                    "properties": {
                        "hs_note_body": note_body,
                        "hs_timestamp": str(int(__import__("time").time() * 1000)),
                    }
                },
            )
            note_resp.raise_for_status()
            note_id = note_resp.json()["id"]

            assoc_resp = await client.put(
                f"{BASE_URL}/crm/v3/objects/notes/{note_id}/associations/deals/{deal_id}/note_to_deal",
                headers=_headers(),
            )
            assoc_resp.raise_for_status()
            logger.info("hubspot_note_created", deal_id=deal_id, note_id=note_id)
            return True
        except Exception as e:
            logger.error("hubspot_note_failed", deal_id=deal_id, error=str(e))
            return False


# ── Contact name lookup ───────────────────────────────────────────────────────

async def get_contact_first_name_by_phone(phone: str) -> str:
    """
    Search HubSpot contacts by phone number and return the first name.
    Matches on last 10 digits to handle country-code variations (+1, etc.).
    Returns empty string if not found or on any error.
    """
    if settings.demo_mode:
        return ""

    digits = re.sub(r"\D", "", phone)
    search_value = digits[-10:] if len(digits) >= 10 else digits
    if not search_value:
        return ""

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/crm/v3/objects/contacts/search",
                headers=_headers(),
                json={
                    # OR across phone and mobilephone fields
                    "filterGroups": [
                        {"filters": [{"propertyName": "phone",
                                       "operator": "CONTAINS_TOKEN",
                                       "value": search_value}]},
                        {"filters": [{"propertyName": "mobilephone",
                                       "operator": "CONTAINS_TOKEN",
                                       "value": search_value}]},
                    ],
                    "properties": ["firstname"],
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                first = results[0]["properties"].get("firstname") or ""
                logger.info("contact_name_found", phone=phone, first_name=first)
                return first
        except Exception as e:
            logger.warning("contact_phone_lookup_failed", phone=phone, error=str(e))
    return ""


# ── Test order update ─────────────────────────────────────────────────────────

TEST_ORDER_NAME = "Alejandro Pending Verification"


async def complete_test_order(deal_name_hint: str = "") -> bool:
    """
    Find a pending deal by name and mark it completed.
    Uses deal_name_hint (e.g. "12345 Alejandro Pending") to build search filters.
    """
    if settings.demo_mode:
        logger.info("demo_test_order_completed")
        return True

    # Extract meaningful word tokens from the hint (skip pure numbers)
    hint_words = [w for w in deal_name_hint.split() if w and not w.isdigit()] if deal_name_hint else []
    # Always anchor on "Pending"; add up to 2 words from the hint
    search_words = list(dict.fromkeys(hint_words[:2] + ["Pending"]))

    filters = [
        {"propertyName": "dealname", "operator": "CONTAINS_TOKEN", "value": w}
        for w in search_words
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/crm/v3/objects/deals/search",
                headers=_headers(),
                json={
                    "filterGroups": [{"filters": filters}],
                    "properties": ["dealname"],
                    "limit": 10,
                },
            )
            resp.raise_for_status()
            all_results = resp.json().get("results", [])

            logger.info("hubspot_deals_found", count=len(all_results),
                        names=[r["properties"].get("dealname", "") for r in all_results])

            # Python-side: deal name must contain "pending"
            results = [
                r for r in all_results
                if "pending" in r["properties"].get("dealname", "").lower()
            ]

            if not results:
                logger.warning("test_order_not_found", hint=deal_name_hint,
                               all_names=[r["properties"].get("dealname", "") for r in all_results])
                return False

            deal = results[0]
            deal_id = deal["id"]
            current_name = deal["properties"].get("dealname", "")

            if "pending" not in current_name.lower():
                logger.warning("test_order_safety_guard", deal_name=current_name)
                return False

            # Rename: replace "Pending Verification" or just "Pending" → "Completed"
            if "Pending Verification" in current_name:
                new_name = current_name.replace("Pending Verification", "Completed")
            elif "Pending" in current_name:
                new_name = current_name.replace("Pending", "Completed")
            else:
                new_name = current_name + " (Completed)"

            patch = await client.patch(
                f"{BASE_URL}/crm/v3/objects/deals/{deal_id}",
                headers=_headers(),
                json={"properties": {"dealname": new_name}},
            )
            patch.raise_for_status()

            logger.info(
                "test_call_completed_hubspot_updated",
                message="AI verification completed. HubSpot order updated to Completed.",
                deal_id=deal_id,
                old_name=current_name,
                new_name=new_name,
            )
            return True

        except Exception as e:
            logger.error("test_order_update_failed", error=str(e))
            return False


# ── Demo data ──────────────────────────────────────────────────────────────────

def _demo_deals() -> list[HubSpotDeal]:
    return [
        HubSpotDeal(
            deal_id="DEMO-001",
            deal_name=f"Magento Order 100001999 from John Smith {TAG_PENDING}",
            fraud_status=TAG_PENDING,
            contact_phone="+15551234567",
            contact_name="John Smith",
            contact_email="john.smith@example.com",
            contact_id="CONTACT-001",
            amount="1200.00",
        ),
        HubSpotDeal(
            deal_id="DEMO-002",
            deal_name=f"Magento Order 100002000 from Jane Doe {TAG_PENDING}",
            fraud_status=TAG_PENDING,
            contact_phone="+15559876543",
            contact_name="Jane Doe",
            contact_email="jane.doe@example.com",
            contact_id="CONTACT-002",
            amount="450.00",
        ),
        HubSpotDeal(
            deal_id="DEMO-003",
            deal_name=f"Magento Order 100002001 from Unknown Caller {TAG_PENDING}",
            fraud_status=TAG_PENDING,
            contact_phone="+15550001111",
            contact_name="Unknown Caller",
            contact_email="fake@scam.com",
            contact_id="CONTACT-003",
            amount="5000.00",
        ),
    ]
