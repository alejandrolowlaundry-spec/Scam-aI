from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_sid: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # HubSpot linkage
    hubspot_deal_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    hubspot_contact_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hubspot_updated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Call metadata
    from_number: Mapped[str] = mapped_column(String(32))
    to_number: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(16), default="outbound")  # inbound / outbound
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="initiated")

    # Recording / Transcript
    recording_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recording_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Analysis results
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_label: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)   # low/medium/high
    fraud_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Safe Customer/Suspicious/Confirmed Scam
    reasons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    signals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_claude_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Alerts
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
