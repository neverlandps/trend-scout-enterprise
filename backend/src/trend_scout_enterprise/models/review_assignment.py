"""Review assignment model mapping workspace categories to reviewers."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class ReviewAssignment(Base):
    """Assigns a reviewer to a source category within a workspace."""

    __tablename__ = "review_assignments"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    category = Column(String(100), nullable=False)
    reviewer_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    workspace = relationship("Workspace")
    reviewer = relationship("ApiKey")

    __table_args__ = (
        UniqueConstraint("workspace_id", "category", name="uq_review_assignments_ws_category"),
        Index("ix_review_assignments_workspace_id", "workspace_id"),
    )
