"""Signal API endpoints for listing and analyzing raw items."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, LlmProvider, RawItem, Source, Workspace
from trend_scout_enterprise.schemas import (
    RawItemOut,
    SignalAnalyzeOut,
    SignalAnalyzeRequest,
    SignalListOut,
)
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch
from trend_scout_enterprise.services.llm_service import LlmService
from trend_scout_enterprise.core.encryption import decrypt_value

router = APIRouter()


def _get_default_llm_service(db: Session) -> LlmService:
    """Build an LlmService from the default LLM provider in the database."""
    provider = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No default LLM provider configured",
        )
    api_key = None
    if provider.api_key_encrypted:
        try:
            api_key = decrypt_value(provider.api_key_encrypted)
        except Exception:
            api_key = None
    return LlmService(
        base_url=provider.base_url,
        api_key=api_key,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
    )


@router.get("/signals", response_model=SignalListOut)
def list_signals(
    source_id: str | None = None,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SignalListOut:
    """List raw signals in the current workspace."""
    query = db.query(RawItem).filter(RawItem.workspace_id == workspace.id)
    if source_id:
        query = query.filter(RawItem.source_id == source_id)
    if min_score is not None:
        query = query.filter(RawItem.overall_score >= min_score)
    total = query.count()
    signals = (
        query.order_by(RawItem.collected_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SignalListOut(signals=signals, total=total)


@router.get("/signals/{signal_id}", response_model=RawItemOut)
def get_signal(
    signal_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> RawItemOut:
    """Retrieve a single signal by ID in the current workspace."""
    signal = (
        db.query(RawItem)
        .filter(RawItem.id == signal_id, RawItem.workspace_id == workspace.id)
        .first()
    )
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    return signal


@router.post("/signals/analyze", response_model=SignalAnalyzeOut)
async def analyze_signals(
    request: SignalAnalyzeRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SignalAnalyzeOut:
    """Analyze selected signals using the configured LLM provider."""
    items = (
        db.query(RawItem)
        .filter(RawItem.id.in_(request.item_ids), RawItem.workspace_id == workspace.id)
        .all()
    )
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No signals found")

    llm_service = _get_default_llm_service(db)
    result = await analyze_signals_batch(db, [item.id for item in items], llm_service)
    return SignalAnalyzeOut(**result)
