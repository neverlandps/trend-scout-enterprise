from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    owner_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    title = Column(String(500))
    report_type = Column(String(50), default="pdf")
    status = Column(String(20), default="generating")
    file_path = Column(Text)
    summary_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(JSON, default=dict)

    owner = relationship("ApiKey", back_populates="reports")
    workspace = relationship("Workspace")
