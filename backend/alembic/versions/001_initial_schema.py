"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("call_sid", sa.String(64), nullable=False, unique=True),
        sa.Column("hubspot_deal_id", sa.String(64), nullable=True),
        sa.Column("hubspot_contact_id", sa.String(64), nullable=True),
        sa.Column("hubspot_updated", sa.Boolean(), default=False),
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), default="outbound"),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), default="initiated"),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("recording_sid", sa.String(64), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_label", sa.String(16), nullable=True),
        sa.Column("fraud_label", sa.String(32), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=True),
        sa.Column("raw_claude_json", sa.JSON(), nullable=True),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_calls_call_sid", "calls", ["call_sid"])
    op.create_index("ix_calls_hubspot_deal_id", "calls", ["hubspot_deal_id"])


def downgrade() -> None:
    op.drop_table("calls")
