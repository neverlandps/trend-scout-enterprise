from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class RawItem(Base):
    __tablename__ = "raw_items"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    title = Column(Text)
    summary = Column(Text)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    relevance_score = Column(Float)
    signal_strength = Column(Float)
    cross_domain_impact = Column(Float)
    investment_velocity = Column(Float)
    technical_feasibility = Column(Float)
    strategic_fit = Column(Float)
    overall_score = Column(Float)
    review_status = Column(String(20), default="auto", index=True)
    human_score = Column(Float, nullable=True)
    assigned_reviewer_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)

    source = relationship("Source")
    workspace = relationship("Workspace")
    assigned_reviewer = relationship("ApiKey")
    reviews = relationship(
        "SignalReview", back_populates="raw_item", cascade="all, delete-orphan"
    )
