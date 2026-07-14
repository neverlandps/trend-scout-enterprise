from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class WorkspaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceSwitch(BaseModel):
    workspace_id: str


class TeamMemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., pattern="^(admin|analyst|viewer)$")
    workspace_id: str | None = None


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: str
    key_prefix: str
    is_active: bool
    created_at: datetime


class TeamMemberWithKeyOut(BaseModel):
    id: str
    name: str
    role: str
    api_key: str
    key_prefix: str
    created_at: datetime
