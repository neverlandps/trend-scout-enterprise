"""Workspace, team, and access-control service."""

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import ApiKey, Team, TeamMembership, Workspace
from trend_scout_enterprise.core.security import generate_api_key, hash_api_key, get_key_prefix


DEFAULT_TEAM_NAME = "Default Team"
DEFAULT_WORKSPACE_NAME = "Default Workspace"


def get_or_create_default_team_workspace(db: Session, api_key: ApiKey) -> Workspace:
    """Return the default workspace for an API key, creating team + workspace if needed.

    Also migrates legacy resources (created before workspace isolation) by assigning
    them to the default workspace.
    """
    membership = db.query(TeamMembership).filter(TeamMembership.api_key_id == api_key.id).first()

    if membership:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.team_id == membership.team_id, Workspace.is_default == True)
            .first()
        )
        if workspace:
            _migrate_legacy_resources(db, workspace)
            return workspace

    # Create default team and workspace
    team = Team(id=uuid4().hex, name=DEFAULT_TEAM_NAME, slug=f"default-{uuid4().hex[:8]}")
    db.add(team)
    db.flush()

    workspace = Workspace(
        id=uuid4().hex,
        team_id=team.id,
        name=DEFAULT_WORKSPACE_NAME,
        is_default=True,
    )
    db.add(workspace)
    db.flush()

    membership = TeamMembership(
        id=uuid4().hex,
        team_id=team.id,
        api_key_id=api_key.id,
        role="admin",
    )
    db.add(membership)
    db.commit()

    _migrate_legacy_resources(db, workspace)
    db.commit()
    return workspace


def _migrate_legacy_resources(db: Session, workspace: Workspace) -> None:
    """Assign any resource with a NULL workspace_id to the default workspace."""
    from trend_scout_enterprise.models.models import Source, ScanRun, RawItem, ScoringProfile, Report
    from trend_scout_enterprise.models.schedule import ScanSchedule, NotificationChannel
    from trend_scout_enterprise.models.sharepoint import SharePointConnection

    for model in [Source, ScanRun, RawItem, ScoringProfile, Report, ScanSchedule, NotificationChannel, SharePointConnection]:
        for row in db.query(model).filter(getattr(model, "workspace_id", None) == None):
            row.workspace_id = workspace.id
    db.commit()


def resolve_workspace(db: Session, api_key: ApiKey, workspace_id: str | None = None) -> Workspace:
    """Resolve the requested workspace for an API key, checking membership."""
    membership = db.query(TeamMembership).filter(TeamMembership.api_key_id == api_key.id).first()
    if not membership:
        # Auto-create a default team/workspace for standalone API keys (e.g., legacy or tests).
        return get_or_create_default_team_workspace(db, api_key)

    if workspace_id:
        workspace = db.query(Workspace).filter(
            Workspace.id == workspace_id,
            Workspace.team_id == membership.team_id,
        ).first()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or not accessible",
            )
        return workspace

    workspace = (
        db.query(Workspace)
        .filter(Workspace.team_id == membership.team_id, Workspace.is_default == True)
        .first()
    )
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default workspace not found",
        )
    return workspace


def list_team_workspaces(db: Session, api_key: ApiKey) -> list[Workspace]:
    """List all workspaces accessible to the API key's team."""
    membership = db.query(TeamMembership).filter(TeamMembership.api_key_id == api_key.id).first()
    if not membership:
        return []
    return db.query(Workspace).filter(Workspace.team_id == membership.team_id).all()


def require_admin(api_key: ApiKey) -> None:
    """Raise 403 if the API key is not a team admin."""
    if api_key.role != "admin":
        membership = getattr(api_key, "membership", None)
        if not membership or membership.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required",
            )


def create_team_api_key(
    db: Session,
    admin_key: ApiKey,
    name: str,
    role: str,
    workspace_id: str | None = None,
) -> tuple[str, ApiKey]:
    """Create a new API key for the admin's team and optionally assign it to a workspace."""
    require_admin(admin_key)
    admin_membership = db.query(TeamMembership).filter(
        TeamMembership.api_key_id == admin_key.id
    ).first()
    if not admin_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin is not associated with any team",
        )

    if role not in {"admin", "analyst", "viewer"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be admin, analyst, or viewer",
        )

    plaintext = generate_api_key()
    new_key = ApiKey(
        id=uuid4().hex,
        name=name,
        key_hash=hash_api_key(plaintext),
        key_prefix=get_key_prefix(plaintext),
        is_active=True,
        role=role,
    )
    db.add(new_key)
    db.flush()

    membership = TeamMembership(
        id=uuid4().hex,
        team_id=admin_membership.team_id,
        api_key_id=new_key.id,
        role=role,
    )
    db.add(membership)

    if workspace_id:
        workspace = db.query(Workspace).filter(
            Workspace.id == workspace_id,
            Workspace.team_id == admin_membership.team_id,
        ).first()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
    db.commit()
    db.refresh(new_key)
    return plaintext, new_key


def list_team_members(db: Session, admin_key: ApiKey) -> list[ApiKey]:
    """List all API keys in the admin's team."""
    require_admin(admin_key)
    membership = db.query(TeamMembership).filter(TeamMembership.api_key_id == admin_key.id).first()
    if not membership:
        return []
    return (
        db.query(ApiKey)
        .join(TeamMembership, TeamMembership.api_key_id == ApiKey.id)
        .filter(TeamMembership.team_id == membership.team_id)
        .all()
    )


def create_workspace(db: Session, admin_key: ApiKey, name: str) -> Workspace:
    """Create a new workspace within the admin's team."""
    require_admin(admin_key)
    membership = db.query(TeamMembership).filter(TeamMembership.api_key_id == admin_key.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin is not associated with any team",
        )

    workspace = Workspace(
        id=uuid4().hex,
        team_id=membership.team_id,
        name=name,
        is_default=False,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def can_write(role: str) -> bool:
    return role in {"admin", "analyst"}


def can_read(role: str) -> bool:
    return role in {"admin", "analyst", "viewer"}
