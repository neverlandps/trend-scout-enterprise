from fastapi import APIRouter

router = APIRouter()


@router.get("/settings/llm")
def get_llm_settings():
    return {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 4096,
    }


@router.put("/settings/llm")
def update_llm_settings(settings: dict):
    return {"updated": True, "settings": settings}


@router.get("/settings/scoring")
def get_scoring_settings():
    return {
        "dimensions": [
            {"name": "signal_strength", "weight": 0.25, "enabled": True},
            {"name": "cross_domain_impact", "weight": 0.20, "enabled": True},
            {"name": "investment_velocity", "weight": 0.20, "enabled": True},
            {"name": "technical_feasibility", "weight": 0.20, "enabled": True},
            {"name": "strategic_fit", "weight": 0.15, "enabled": True},
        ]
    }


@router.put("/settings/scoring")
def update_scoring_settings(settings: dict):
    return {"updated": True, "settings": settings}
