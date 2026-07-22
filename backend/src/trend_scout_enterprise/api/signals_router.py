"""Signal API endpoints for listing and analyzing raw items."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.audit import record_audit
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import (
    get_current_api_key,
    get_current_workspace,
    get_current_workspace_unified,
)
from trend_scout_enterprise.core.encryption import decrypt_value
from trend_scout_enterprise.models.models import ApiKey, LlmProvider, RawItem, Source, Workspace
from trend_scout_enterprise.models.signal_embedding import SignalEmbedding
from trend_scout_enterprise.models.signal_review import SignalReview
from trend_scout_enterprise.schemas import (
    BulkReviewFailure,
    BulkReviewRequest,
    BulkReviewResult,
    FeedbackRequest,
    RawItemOut,
    ReviewActionRequest,
    ReviewOut,
    SemanticSearchOut,
    SignalAnalyzeOut,
    SignalAnalyzeRequest,
    SignalListOut,
    SimilarSignalOut,
)
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch
from trend_scout_enterprise.services.embedding_service import EmbeddingService, top_k_similar
from trend_scout_enterprise.services.llm_service import LlmService

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
    review_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> SignalListOut:
    """List raw signals in the current workspace."""
    query = db.query(RawItem).filter(RawItem.workspace_id == workspace.id)
    if source_id:
        query = query.filter(RawItem.source_id == source_id)
    if min_score is not None:
        query = query.filter(RawItem.overall_score >= min_score)
    if review_status:
        query = query.filter(RawItem.review_status == review_status)
    total = query.count()
    signals = (
        query.order_by(RawItem.collected_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SignalListOut(signals=signals, total=total)


# ---------------------------------------------------------------------------
# Human-in-the-loop review workflow
# ---------------------------------------------------------------------------

_ACTION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "flag": "flagged",
    "override": "approved",
}


def _get_workspace_signal(db: Session, signal_id: str, workspace_id: str) -> RawItem:
    """Fetch a signal scoped to the workspace or raise 404."""
    signal = (
        db.query(RawItem)
        .filter(RawItem.id == signal_id, RawItem.workspace_id == workspace_id)
        .first()
    )
    if not signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    return signal


def _apply_review_action(
    db: Session,
    item: RawItem,
    action: str,
    reviewer_id: str,
    human_score: float | None = None,
    notes: str | None = None,
) -> SignalReview:
    """Apply a review action to an item and record a SignalReview entry."""
    if action == "override" and human_score is None:
        raise ValueError("human_score is required for override")
    item.review_status = _ACTION_TO_STATUS[action]
    if action == "override":
        item.human_score = human_score
    review = SignalReview(
        id=uuid4().hex,
        raw_item_id=item.id,
        workspace_id=item.workspace_id,
        reviewer_id=reviewer_id,
        status=_ACTION_TO_STATUS[action],
        human_score=human_score,
        notes=notes,
    )
    db.add(review)
    return review


@router.get("/signals/review-queue", response_model=SignalListOut)
def get_review_queue(
    source_id: str | None = None,
    category: str | None = None,
    assigned_to_me: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SignalListOut:
    """List signals pending human review in the current workspace."""
    query = db.query(RawItem).filter(
        RawItem.workspace_id == workspace.id,
        RawItem.review_status == "pending_review",
    )
    if source_id:
        query = query.filter(RawItem.source_id == source_id)
    if category:
        query = query.join(Source, RawItem.source_id == Source.id).filter(
            Source.category == category
        )
    if assigned_to_me:
        query = query.filter(RawItem.assigned_reviewer_id == api_key.id)
    total = query.count()
    signals = (
        query.order_by(RawItem.collected_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return SignalListOut(signals=signals, total=total)


@router.post("/signals/bulk-review", response_model=BulkReviewResult)
def bulk_review_signals(
    request: BulkReviewRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> BulkReviewResult:
    """Apply a review action to multiple signals in a single transaction."""
    succeeded: list[str] = []
    failed: list[BulkReviewFailure] = []
    for item_id in request.item_ids:
        item = (
            db.query(RawItem)
            .filter(RawItem.id == item_id, RawItem.workspace_id == workspace.id)
            .first()
        )
        if not item:
            failed.append(BulkReviewFailure(id=item_id, error="Signal not found"))
            continue
        try:
            _apply_review_action(
                db, item, request.action, api_key.id, notes=request.notes
            )
            succeeded.append(item_id)
        except ValueError as exc:
            failed.append(BulkReviewFailure(id=item_id, error=str(exc)))
    db.commit()
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="signal.bulk_review",
        workspace_id=workspace.id,
        resource_type="signal",
        detail={
            "action": request.action,
            "total": len(request.item_ids),
            "succeeded": len(succeeded),
        },
    )
    return BulkReviewResult(succeeded=succeeded, failed=failed)


@router.post("/signals/{signal_id}/review", response_model=ReviewOut)
def review_signal(
    signal_id: str,
    request: ReviewActionRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SignalReview:
    """Apply a human review action to a signal in the current workspace."""
    item = _get_workspace_signal(db, signal_id, workspace.id)
    try:
        review = _apply_review_action(
            db, item, request.action, api_key.id,
            human_score=request.human_score, notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    db.commit()
    db.refresh(review)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="signal.review",
        workspace_id=workspace.id,
        resource_type="signal",
        resource_id=item.id,
        detail={"action": request.action, "human_score": request.human_score},
    )
    return review


@router.post("/signals/{signal_id}/feedback", response_model=ReviewOut)
def submit_signal_feedback(
    signal_id: str,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SignalReview:
    """Record reviewer feedback and a human score for a signal."""
    item = _get_workspace_signal(db, signal_id, workspace.id)
    item.human_score = request.human_score
    review = SignalReview(
        id=uuid4().hex,
        raw_item_id=item.id,
        workspace_id=item.workspace_id,
        reviewer_id=api_key.id,
        status="feedback",
        human_score=request.human_score,
        feedback_type=request.feedback_type,
        notes=request.notes,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="signal.feedback",
        workspace_id=workspace.id,
        resource_type="signal",
        resource_id=item.id,
        detail={
            "feedback_type": request.feedback_type,
            "human_score": request.human_score,
        },
    )
    return review


# ---------------------------------------------------------------------------
# Vector search (semantic retrieval)
# ---------------------------------------------------------------------------


def _require_vector_search_enabled() -> None:
    """Raise 503 when the vector search feature flag is off."""
    if not settings.vector_search_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector search is disabled",
        )


def _workspace_embeddings(db: Session, workspace_id: str) -> list[SignalEmbedding]:
    return (
        db.query(SignalEmbedding)
        .filter(SignalEmbedding.workspace_id == workspace_id)
        .all()
    )


@router.get("/signals/semantic-search", response_model=SemanticSearchOut)
async def semantic_search_signals(
    q: str,
    limit: int = 20,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom, matches this module
    workspace: Workspace = Depends(get_current_workspace_unified),  # noqa: B008
) -> SemanticSearchOut:
    """Search signals semantically by embedding the query and ranking by cosine similarity."""
    _require_vector_search_enabled()
    if not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query must not be empty"
        )
    llm_service = _get_default_llm_service(db)
    embedding_service = EmbeddingService(llm_service)
    query_vector = (await embedding_service.embed_texts([q]))[0]

    rows = _workspace_embeddings(db, workspace.id)
    ranked = top_k_similar(query_vector, rows, limit)
    return SemanticSearchOut(
        query=q,
        results=[
            SimilarSignalOut(signal=RawItemOut.model_validate(row.raw_item), similarity=score)
            for row, score in ranked
        ],
    )


@router.get("/signals/{signal_id}/similar", response_model=list[SimilarSignalOut])
def get_similar_signals(
    signal_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency idiom, matches this module
    workspace: Workspace = Depends(get_current_workspace_unified),  # noqa: B008
) -> list[SimilarSignalOut]:
    """Return signals most similar to the given signal by embedding cosine similarity."""
    _require_vector_search_enabled()
    signal = _get_workspace_signal(db, signal_id, workspace.id)

    reference = (
        db.query(SignalEmbedding)
        .filter(SignalEmbedding.raw_item_id == signal.id)
        .first()
    )
    if not reference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal has no embedding; run a scan with vector search enabled first",
        )

    rows = [
        row
        for row in _workspace_embeddings(db, workspace.id)
        if row.raw_item_id != signal.id
    ]
    ranked = top_k_similar(list(reference.embedding or []), rows, limit)
    return [
        SimilarSignalOut(signal=RawItemOut.model_validate(row.raw_item), similarity=score)
        for row, score in ranked
    ]


@router.get("/signals/{signal_id}", response_model=RawItemOut)
def get_signal(
    signal_id: str,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
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
