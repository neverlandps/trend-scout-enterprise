"""Embedding service for dialect-agnostic vector search over signals.

Embeddings come from the same OpenAI-compatible providers as chat (the
``POST {base_url}/embeddings`` endpoint) and are stored as JSON float lists;
cosine similarity is computed in pure Python. This keeps SQLite and
PostgreSQL on the same code path with zero infrastructure dependencies.
Acceptable for corpora in the low tens of thousands of signals; beyond that,
migrate storage/similarity to pgvector on PostgreSQL as an optimization.
"""

import math
import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.raw_item import RawItem
from trend_scout_enterprise.models.signal_embedding import SignalEmbedding
from trend_scout_enterprise.services.llm_service import LlmProviderConfig, LlmService

logger = structlog.get_logger(__name__)

MAX_TEXTS_PER_REQUEST = 32
MAX_TEXT_CHARS = 8000


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def item_to_text(item: RawItem) -> str:
    """Build the embedding input text for a raw item, truncated to a safe size."""
    text = f"{item.title or ''}\n{item.summary or ''}".strip()
    return text[:MAX_TEXT_CHARS]


class EmbeddingService:
    """Generate embeddings via the configured LLM provider fallback chain."""

    def __init__(self, llm_service: LlmService, model: str | None = None) -> None:
        self.llm_service = llm_service
        self.model = model or settings.embedding_model

    def _providers(self) -> list[LlmProviderConfig]:
        """Primary provider plus the configured fallback chain."""
        return [self.llm_service._primary_provider()] + list(
            self.llm_service.fallback_providers
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, batching at most 32 texts per API request."""
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), MAX_TEXTS_PER_REQUEST):
            batch = texts[start : start + MAX_TEXTS_PER_REQUEST]
            embeddings.extend(await self._embed_batch(batch))
        return embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed one batch, falling back to configured providers on failure."""
        last_error: Exception | None = None
        for provider in self._providers():
            try:
                async with httpx.AsyncClient(timeout=provider.timeout) as client:
                    response = await client.post(
                        f"{provider.base_url}/embeddings",
                        headers=provider.to_headers(),
                        json={"model": self.model, "input": texts},
                    )
                    response.raise_for_status()
                    data = response.json()
                entries = sorted(data.get("data", []), key=lambda e: e.get("index", 0))
                return [list(map(float, entry["embedding"])) for entry in entries]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise last_error or RuntimeError("All embedding providers failed")

    async def generate_for_items(
        self, db: Session, items: list[RawItem]
    ) -> dict[str, int]:
        """Generate and store embeddings for items that do not have one yet.

        Existing embeddings are left untouched, so repeated runs are
        idempotent. Returns ``{"embedded": n, "failed": m}``.
        """
        if not items:
            return {"embedded": 0, "failed": 0}

        item_ids = [item.id for item in items]
        existing_ids = {
            row.raw_item_id
            for row in db.query(SignalEmbedding.raw_item_id)
            .filter(SignalEmbedding.raw_item_id.in_(item_ids))
            .all()
        }
        pending = [item for item in items if item.id not in existing_ids]
        if not pending:
            return {"embedded": 0, "failed": 0}

        try:
            vectors = await self.embed_texts([item_to_text(item) for item in pending])
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "embedding_generation_failed",
                items=len(pending),
                error=str(exc),
            )
            return {"embedded": 0, "failed": len(pending)}

        embedded = 0
        for item, vector in zip(pending, vectors, strict=False):
            try:
                row = (
                    db.query(SignalEmbedding)
                    .filter(SignalEmbedding.raw_item_id == item.id)
                    .first()
                )
                if row:
                    row.embedding = vector
                    row.model = self.model
                else:
                    db.add(
                        SignalEmbedding(
                            id=uuid.uuid4().hex,
                            raw_item_id=item.id,
                            workspace_id=item.workspace_id,
                            embedding=vector,
                            model=self.model,
                        )
                    )
                embedded += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "embedding_store_failed", raw_item_id=item.id, error=str(exc)
                )
        db.commit()
        return {"embedded": embedded, "failed": len(pending) - embedded}


def top_k_similar(
    query_vector: list[float],
    rows: list[Any],
    limit: int,
) -> list[tuple[Any, float]]:
    """Rank embedding rows by cosine similarity to the query vector.

    Pure-Python full scan; swap for a pgvector ``ORDER BY embedding <=> :q``
    query when moving to PostgreSQL at scale.
    """
    scored = [
        (row, cosine_similarity(query_vector, list(row.embedding or [])))
        for row in rows
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
