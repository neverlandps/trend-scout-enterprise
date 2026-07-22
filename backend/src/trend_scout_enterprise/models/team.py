from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspaces = relationship("Workspace", back_populates="team", cascade="all, delete-orphan")
    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False, unique=True)
    role = Column(String(50), nullable=False, default="analyst")
    joined_at = Column(DateTime, server_default=func.now())

    team = relationship("Team", back_populates="memberships")
    api_key = relationship("ApiKey", back_populates="membership")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    team = relationship("Team", back_populates="workspaces")

    __table_args__ = (Index("ix_workspaces_team_id", "team_id"),)
