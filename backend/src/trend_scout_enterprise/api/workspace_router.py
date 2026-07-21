"""Workspace and team membership API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.audit import record_audit
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.core.rate_limit import limiter
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.schemas.workspace import (
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberWithKeyOut,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceSwitch,
)
from trend_scout_enterprise.services import workspace_service

router = APIRouter()


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> list[WorkspaceOut]:
    """List workspaces accessible to the authenticated API key."""
    workspaces = workspace_service.list_team_workspaces(db, api_key)
    return [WorkspaceOut.model_validate(w) for w in workspaces]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> WorkspaceOut:
    """Create a new workspace (admin only)."""
    workspace = workspace_service.create_workspace(db, api_key, payload.name)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="workspace.create",
        workspace_id=workspace.id,
        resource_type="workspace",
        resource_id=workspace.id,
        detail={"name": payload.name},
    )
    return WorkspaceOut.model_validate(workspace)


@router.get("/workspaces/current", response_model=WorkspaceOut)
def get_current_workspace(
    workspace: Workspace = Depends(get_current_workspace),
) -> WorkspaceOut:
    """Return the currently selected or default workspace."""
    return WorkspaceOut.model_validate(workspace)


@router.post("/workspaces/switch", response_model=WorkspaceOut)
def switch_workspace(
    payload: WorkspaceSwitch,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> WorkspaceOut:
    """Validate and return the requested workspace."""
    workspace = workspace_service.resolve_workspace(db, api_key, payload.workspace_id)
    return WorkspaceOut.model_validate(workspace)


@router.get("/team/members", response_model=list[TeamMemberOut])
def list_team_members(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> list[TeamMemberOut]:
    """List team members (admin only)."""
    members = workspace_service.list_team_members(db, api_key)
    return [TeamMemberOut.model_validate(m) for m in members]


@router.post("/team/members", response_model=TeamMemberWithKeyOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_team_member(
    request: Request,
    payload: TeamMemberCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> TeamMemberWithKeyOut:
    """Invite a new team member by creating an API key (admin only)."""
    plaintext, new_key = workspace_service.create_team_api_key(
        db, api_key, payload.name, payload.role, payload.workspace_id
    )
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="team.member.create",
        workspace_id=payload.workspace_id,
        resource_type="api_key",
        resource_id=new_key.id,
        detail={"name": payload.name, "role": payload.role},
    )
    return TeamMemberWithKeyOut(
        id=new_key.id,
        name=new_key.name,
        role=payload.role,
        api_key=plaintext,
        key_prefix=new_key.key_prefix,
        created_at=new_key.created_at,
    )
