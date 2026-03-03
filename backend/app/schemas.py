from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ── Fraud Analysis ─────────────────────────────────────────────────────────────

class FraudSignals(BaseModel):
    keywords: list[str] = []
    pressure_tactics: list[str] = []
    spoofing_suspected: bool = False
    inconsistencies: list[str] = []
    script_match: list[str] = []


class FraudAnalysisResult(BaseModel):
    risk_score: int = Field(..., ge=0, le=100)
    risk_label: Literal["low", "medium", "high"]
    fraud_label: Literal["Safe Customer", "Suspicious", "Confirmed Scam"]
    reasons: list[str]
    signals: FraudSignals
    summary: str
    confidence: Literal["low", "medium", "high"]


# ── Call Schemas ───────────────────────────────────────────────────────────────

class CallBase(BaseModel):
    call_sid: str
    from_number: str
    to_number: str
    direction: str
    status: str


class CallOut(BaseModel):
    id: int
    call_sid: str
    hubspot_deal_id: Optional[str] = None
    from_number: str
    to_number: str
    direction: str
    duration: Optional[int] = None
    status: str
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    risk_score: Optional[int] = None
    risk_label: Optional[str] = None
    fraud_label: Optional[str] = None
    reasons: Optional[list[str]] = None
    signals: Optional[dict] = None
    analysis_summary: Optional[str] = None
    hubspot_updated: bool
    alert_sent: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CallListOut(BaseModel):
    total: int
    calls: list[CallOut]


# ── HubSpot Schemas ────────────────────────────────────────────────────────────

class HubSpotDeal(BaseModel):
    deal_id: str
    deal_name: str
    fraud_status: str
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_id: Optional[str] = None
    amount: Optional[str] = None
    created_at: Optional[str] = None


class HubSpotDealsOut(BaseModel):
    total: int
    deals: list[HubSpotDeal]


class InitiateCallRequest(BaseModel):
    deal_id: str


class InitiateCallOut(BaseModel):
    call_sid: str
    deal_id: str
    phone_number: str
    message: str


# ── Twilio Webhook Payloads ────────────────────────────────────────────────────

class TwilioCallStatusPayload(BaseModel):
    CallSid: str
    CallStatus: str
    From: Optional[str] = None
    To: Optional[str] = None
    Duration: Optional[str] = None
    RecordingUrl: Optional[str] = None
    RecordingSid: Optional[str] = None


class TwilioRecordingPayload(BaseModel):
    CallSid: str
    RecordingSid: str
    RecordingUrl: str
    RecordingDuration: Optional[str] = None
    RecordingStatus: Optional[str] = None


# ── Analytics ─────────────────────────────────────────────────────────────────

class DailyCount(BaseModel):
    date: str
    total: int
    high: int
    medium: int
    low: int


class TopSignal(BaseModel):
    signal: str
    count: int


class AnalyticsSummary(BaseModel):
    total_calls: int
    safe_customers: int
    suspicious: int
    confirmed_scams: int
    avg_risk_score: float
    calls_by_day: list[DailyCount]
    top_signals: list[TopSignal]
