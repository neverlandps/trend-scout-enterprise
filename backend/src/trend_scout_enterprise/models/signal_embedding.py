"""Signal embedding model for dialect-agnostic vector search.

Embeddings are stored as plain JSON float lists and similarity is computed in
Python, so the same schema works on SQLite and PostgreSQL with zero extra
infrastructure. This is acceptable for tens of thousands of signals; if the
corpus grows beyond that, migrate to pgvector (vector column + ANN index) on
PostgreSQL as a follow-up optimization.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class SignalEmbedding(Base):
    """An embedding vector for a raw signal item."""

    __tablename__ = "signal_embeddings"

    id = Column(String(36), primary_key=True)
    raw_item_id = Column(
        String(36), ForeignKey("raw_items.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    embedding = Column(JSON, nullable=False)  # list[float]
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    raw_item = relationship("RawItem")

    __table_args__ = (
        Index("ix_signal_embeddings_raw_item_id", "raw_item_id", unique=True),
        Index("ix_signal_embeddings_workspace_id", "workspace_id"),
    )
