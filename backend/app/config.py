from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Fraud Detection Agent"
    secret_key: str = "change-me-in-production"
    frontend_url: str = "http://localhost:5173"
    public_url: str = ""          # set to ngrok/localtunnel URL so Twilio can reach webhooks
    demo_mode: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./fraud_detection.db"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Claude / Anthropic
    claude_api_key: str = ""
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"

    # OpenAI (used when claude key is absent)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # HubSpot — accepts HUBSPOT_API_KEY (requested) or HUBSPOT_ACCESS_TOKEN
    hubspot_api_key: str = ""
    hubspot_access_token: str = ""       # fallback alias
    hubspot_fraud_pending_stage: str = "Pending Verification for Fraud"

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel — conversational, natural
    elevenlabs_model_id: str = "eleven_turbo_v2"

    # AssemblyAI (transcription)
    assemblyai_api_key: str = ""

    # Alerts
    sendgrid_api_key: str = ""
    alert_from_email: str = "alerts@yourcompany.com"
    alert_to_email: str = ""
    alert_to_phone: str = ""             # E.164 format e.g. +15551234567

    # Risk thresholds
    high_risk_threshold: int = 70
    medium_risk_threshold: int = 40

    @property
    def effective_hubspot_token(self) -> str:
        """Resolve HubSpot credential — prefers HUBSPOT_API_KEY."""
        return self.hubspot_api_key or self.hubspot_access_token

    @property
    def effective_claude_key(self) -> str:
        """Resolve Anthropic credential — prefers CLAUDE_API_KEY."""
        return self.claude_api_key or self.anthropic_api_key


settings = Settings()
