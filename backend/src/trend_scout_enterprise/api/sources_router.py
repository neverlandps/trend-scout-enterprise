"""Source management API endpoints using source_service."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import (
    get_current_api_key,
    get_current_workspace,
    get_current_workspace_unified,
)
from trend_scout_enterprise.models.models import ApiKey, Workspace
from trend_scout_enterprise.schemas import (
    ScannerTypeOut,
    SourceCreate,
    SourceHealthOut,
    SourceListOut,
    SourceOut,
    SourceUpdate,
)
from trend_scout_enterprise.scanners import list_scanner_types
from trend_scout_enterprise.services import source_service

router = APIRouter()


@router.get("/sources", response_model=SourceListOut)
def list_sources(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> SourceListOut:
    """List all signal sources in the current workspace."""
    sources = source_service.list_sources(db, workspace_id=workspace.id)
    return SourceListOut(sources=[source_service.source_to_schema(s) for s in sources])


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    source: SourceCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SourceOut:
    """Create a new signal source in the current workspace."""
    db_source = source_service.create_source(db, source, api_key, workspace.id)
    return source_service.source_to_schema(db_source)


@router.get("/sources/scanner-types", response_model=ScannerTypeOut)
def scanner_types(
    _: ApiKey = Depends(get_current_api_key),
) -> ScannerTypeOut:
    """Return the list of supported source/scanner types."""
    return ScannerTypeOut(scanner_types=list_scanner_types())


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(
    source_id: str,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> SourceOut:
    """Retrieve a single source by ID in the current workspace."""
    db_source = source_service.get_source(db, source_id, workspace_id=workspace.id)
    return source_service.source_to_schema(db_source)


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: str,
    source: SourceUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> SourceOut:
    """Update an existing source in the current workspace."""
    db_source = source_service.update_source(db, source_id, source, workspace_id=workspace.id)
    return source_service.source_to_schema(db_source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> None:
    """Delete a source by ID in the current workspace."""
    source_service.delete_source(db, source_id, workspace_id=workspace.id)


@router.get("/sources/{source_id}/health", response_model=SourceHealthOut)
def get_source_health(
    source_id: str,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> SourceHealthOut:
    """Retrieve the health status of a source in the current workspace."""
    db_source = source_service.get_source(db, source_id, workspace_id=workspace.id)
    return SourceHealthOut(
        source_id=db_source.id,
        health_status=db_source.health_status,
        last_scan_at=db_source.last_scan_at,
        last_failure_reason=db_source.last_failure_reason,
        suggested_fix=db_source.suggested_fix,
    )
