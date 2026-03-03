# Fraud Detection Agent

AI-powered call verification system. Pulls **"Pending Verification for Fraud"** deals from HubSpot, dials customers via Twilio, transcribes the call, analyzes with Claude, and automatically updates deal status back in HubSpot.

---

## Architecture

```
HubSpot CRM ──► /hubspot/initiate-call  ──► Twilio Outbound Call
                                                    │
                                         TwiML verification script
                                                    │
                                         Recording complete webhook
                                                    │
                                         AssemblyAI transcription
                                                    │
                                         Claude claude-sonnet-4-5 analysis
                                                    │
                              ┌─────────────────────┼──────────────────┐
                              ▼                     ▼                  ▼
                        SQLite / DB         HubSpot deal update    Email/SMS alert
                              │
                        React dashboard
```

**Stack:** Python 3.11 + FastAPI · SQLAlchemy + Alembic · React 18 + Vite + TailwindCSS

---

## Quickstart (Local / Demo Mode)

### 1. Clone & setup backend

```bash
cd fraud-detection-agent/backend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DEMO_MODE=true to run without real credentials
```

### 2. Run migrations & start API

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API is live at http://localhost:8000
Docs at http://localhost:8000/docs

### 3. Setup frontend

```bash
cd fraud-detection-agent/frontend
npm install
npm run dev
```

Dashboard at http://localhost:5173

---

## HubSpot Setup

1. Go to **Settings → Properties → Deal Properties → Create property**
2. Create a **Single-line text** property:
   - Label: `Fraud Verification Status`
   - Internal name: `fraud_verification_status`

3. Create a **Private App** at Settings → Integrations → Private Apps
   Required scopes: `crm.objects.deals.read`, `crm.objects.deals.write`, `crm.objects.contacts.read`

4. Mark deals as `Pending Verification for Fraud` to populate the verification queue.

**Automatic status updates after calls:**
| Fraud Score | Verdict | HubSpot Status |
|---|---|---|
| 0–39 | Safe Customer | `Verified Customer` |
| 40–69 | Suspicious | `Needs Manual Review` |
| 70–100 | Confirmed Scam | `Scam / Fraud` |

---

## Twilio Setup

1. Buy a phone number in your Twilio Console
2. Under that number's **Voice** settings, set **Status Callback URL** to:
   ```
   https://your-backend.com/webhook/call-status
   ```
3. For inbound calls (optional): set **A Call Comes In** webhook to:
   ```
   https://your-backend.com/webhook/call-status
   ```

---

## Testing Locally

### Test webhook with curl (demo mode)
```bash
# Simulate a recording-complete webhook
curl -X POST http://localhost:8000/webhook/recording-complete \
  -d "CallSid=DEMO-scam-test-001&RecordingSid=RE123&RecordingUrl=https://example.com/rec.mp3&RecordingStatus=completed"

# Check the result
curl http://localhost:8000/calls/DEMO-scam-test-001 | jq .
```

### Trigger a HubSpot call (demo mode)
```bash
curl -X POST http://localhost:8000/hubspot/initiate-call/DEMO-001 | jq .
```

### List all calls
```bash
curl "http://localhost:8000/calls?risk_label=high" | jq .risk_score
```

---

## Deploying to Railway

1. Push repo to GitHub
2. New project → Deploy from GitHub
3. Add env vars in Railway dashboard (copy from `.env.example`)
4. For Postgres: add a Postgres plugin, copy `DATABASE_URL` (change `postgresql://` → `postgresql+asyncpg://`)
5. Redeploy — migrations run automatically on startup

---

## Upgrading to Streaming Transcription

Replace `backend/app/services/transcription.py`'s AssemblyAI polling with:

1. **Twilio Media Streams** — send raw audio via WebSocket to your server
2. **Deepgram real-time** — pipe WebSocket frames for <500ms latency transcription
3. **AssemblyAI real-time** — same pattern

This enables fraud detection *during* the call instead of after, unlocking live intervention.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DEMO_MODE` | — | `true` uses mock data, no real APIs called |
| `DATABASE_URL` | ✓ | SQLite or PostgreSQL connection string |
| `TWILIO_ACCOUNT_SID` | prod | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | prod | Twilio auth token (used for signature verification) |
| `TWILIO_PHONE_NUMBER` | prod | Your Twilio outbound number |
| `ANTHROPIC_API_KEY` | prod | Anthropic API key |
| `HUBSPOT_ACCESS_TOKEN` | prod | HubSpot private app token |
| `ASSEMBLYAI_API_KEY` | prod | AssemblyAI key for transcription |
| `SENDGRID_API_KEY` | optional | SendGrid for email alerts |
| `ALERT_TO_EMAIL` | optional | Recipient for high-risk email alerts |
| `ALERT_TO_PHONE` | optional | Recipient for SMS alerts (E.164) |
| `HIGH_RISK_THRESHOLD` | — | Default 70. Score ≥ this → Confirmed Scam |
| `MEDIUM_RISK_THRESHOLD` | — | Default 40. Score ≥ this → Suspicious |
