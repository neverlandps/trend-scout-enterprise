from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class SharePointConnection(Base):
    __tablename__ = "sharepoint_connections"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    site_id = Column(String(255))
    site_url = Column(Text)
    list_id = Column(String(255))
    drive_id = Column(String(255))
    tenant_id = Column(String(255), nullable=False)
    client_id = Column(String(255), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    owner_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)

    owner = relationship("ApiKey", back_populates="sharepoint_connections")
    workspace = relationship("Workspace")



class SharePointUploadRecord(Base):
    __tablename__ = "sharepoint_upload_records"

    id = Column(String(36), primary_key=True)
    report_id = Column(String(36), nullable=False)
    sharepoint_connection_id = Column(String(36), nullable=False)
    web_url = Column(Text)
    item_id = Column(String(255))
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
