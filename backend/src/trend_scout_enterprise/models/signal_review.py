"""Signal review model for the human-in-the-loop review workflow."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class SignalReview(Base):
    """A human review decision recorded for a raw signal item."""

    __tablename__ = "signal_reviews"

    id = Column(String(36), primary_key=True)
    raw_item_id = Column(String(36), ForeignKey("raw_items.id"), nullable=False)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    reviewer_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)
    status = Column(String(20), nullable=False)  # approved/rejected/flagged/feedback
    human_score = Column(Float, nullable=True)
    feedback_type = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    raw_item = relationship("RawItem", back_populates="reviews")
    workspace = relationship("Workspace")
    reviewer = relationship("ApiKey")

    __table_args__ = (
        Index("ix_signal_reviews_raw_item_id", "raw_item_id"),
        Index("ix_signal_reviews_workspace_id", "workspace_id"),
    )
