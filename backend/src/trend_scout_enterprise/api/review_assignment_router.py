"""Review assignment management API endpoints.

Review assignments route pending_review signals to a designated reviewer
based on (workspace_id, category). Admin role required.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.api_key import ApiKey
from trend_scout_enterprise.models.models import TeamMembership, Workspace
from trend_scout_enterprise.models.review_assignment import ReviewAssignment
from trend_scout_enterprise.schemas.schemas import (
    ReviewAssignmentCreate,
    ReviewAssignmentOut,
)
from trend_scout_enterprise.services import workspace_service

router = APIRouter()


def _require_admin(api_key: ApiKey) -> None:
    workspace_service.require_admin(api_key)


def _reviewer_in_team(db: Session, api_key: ApiKey, reviewer_id: str) -> bool:
    """Check the reviewer belongs to the same team as the admin."""
    admin_membership = (
        db.query(TeamMembership).filter(TeamMembership.api_key_id == api_key.id).first()
    )
    if not admin_membership:
        return False
    reviewer_membership = (
        db.query(TeamMembership).filter(TeamMembership.api_key_id == reviewer_id).first()
    )
    return bool(reviewer_membership and reviewer_membership.team_id == admin_membership.team_id)


@router.get("/review-assignments", response_model=list[ReviewAssignmentOut])
def list_assignments(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> list[ReviewAssignmentOut]:
    """List review assignments for the current workspace."""
    rows = (
        db.query(ReviewAssignment)
        .filter(ReviewAssignment.workspace_id == workspace.id)
        .order_by(ReviewAssignment.category)
        .all()
    )
    return [ReviewAssignmentOut.model_validate(r) for r in rows]


@router.post(
    "/review-assignments",
    response_model=ReviewAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: ReviewAssignmentCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ReviewAssignmentOut:
    """Assign a reviewer to a category (admin only). Upserts on conflict."""
    _require_admin(api_key)
    if not _reviewer_in_team(db, api_key, payload.reviewer_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer must be a member of your team",
        )

    existing = (
        db.query(ReviewAssignment)
        .filter(
            ReviewAssignment.workspace_id == workspace.id,
            ReviewAssignment.category == payload.category,
        )
        .first()
    )
    if existing:
        existing.reviewer_id = payload.reviewer_id
        db.commit()
        db.refresh(existing)
        return ReviewAssignmentOut.model_validate(existing)

    import uuid

    assignment = ReviewAssignment(
        id=uuid.uuid4().hex,
        workspace_id=workspace.id,
        category=payload.category,
        reviewer_id=payload.reviewer_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return ReviewAssignmentOut.model_validate(assignment)


@router.delete("/review-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> None:
    """Remove a review assignment (admin only)."""
    _require_admin(api_key)
    assignment = (
        db.query(ReviewAssignment)
        .filter(
            ReviewAssignment.id == assignment_id,
            ReviewAssignment.workspace_id == workspace.id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review assignment not found",
        )
    db.delete(assignment)
    db.commit()
