from app.config import settings


def get_risk_label(score: int) -> str:
    if score < settings.medium_risk_threshold:
        return "low"
    elif score < settings.high_risk_threshold:
        return "medium"
    return "high"


def get_fraud_label(score: int) -> str:
    if score < settings.medium_risk_threshold:
        return "Safe Customer"
    elif score < settings.high_risk_threshold:
        return "Suspicious"
    return "Confirmed Scam"


def get_hubspot_deal_status(fraud_label: str) -> str:
    mapping = {
        "Safe Customer": "Verified Customer",
        "Suspicious": "Needs Manual Review",
        "Confirmed Scam": "Scam / Fraud",
    }
    return mapping.get(fraud_label, "Needs Manual Review")
