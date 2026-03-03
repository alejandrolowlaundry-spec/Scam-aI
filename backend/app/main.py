from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.utils.logging import setup_logging, logger
from app.routers import webhooks, calls, analytics, hubspot, twiml, audio, testing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    logger.info("fraud_detection_agent_started", demo_mode=settings.demo_mode)
    yield
    logger.info("fraud_detection_agent_stopped")


app = FastAPI(
    title="Fraud Detection Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])
app.include_router(twiml.router, prefix="/twiml", tags=["TwiML"])
app.include_router(audio.router, prefix="/audio", tags=["Audio"])
app.include_router(calls.router, prefix="/calls", tags=["Calls"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(hubspot.router, prefix="/hubspot", tags=["HubSpot"])
app.include_router(testing.router, prefix="/testing", tags=["Testing"])


@app.get("/health")
async def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}
