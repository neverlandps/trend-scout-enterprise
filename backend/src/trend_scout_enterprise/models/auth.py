from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class MicrosoftAuthConfig(Base):
    __tablename__ = "microsoft_auth_configs"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, default="default")
    tenant_id = Column(String(255), nullable=False)
    client_id = Column(String(255), nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)
    redirect_uri = Column(Text, nullable=False)
    is_enabled = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(255), nullable=False)
    entra_object_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    token_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
