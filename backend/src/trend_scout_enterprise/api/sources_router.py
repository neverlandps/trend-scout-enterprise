"""Source management API endpoints using source_service."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import verify_api_key
from trend_scout_enterprise.schemas import SourceCreate, SourceListOut, SourceOut, SourceUpdate
from trend_scout_enterprise.services import source_service

router = APIRouter()


@router.get("/sources", response_model=SourceListOut)
def list_sources(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SourceListOut:
    """List all signal sources.

    Args:
        db: SQLAlchemy session.

    Returns:
        SourceListOut containing all sources.
    """
    sources = source_service.list_sources(db)
    return SourceListOut(sources=sources)


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    source: SourceCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SourceOut:
    """Create a new signal source.

    Args:
        source: Source creation payload.
        db: SQLAlchemy session.

    Returns:
        The created source.
    """
    db_source = source_service.create_source(db, source)
    return db_source


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(
    source_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SourceOut:
    """Retrieve a single source by ID.

    Args:
        source_id: UUID of the source.
        db: SQLAlchemy session.

    Returns:
        The requested source.
    """
    return source_service.get_source(db, source_id)


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: str,
    source: SourceUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> SourceOut:
    """Update an existing source.

    Args:
        source_id: UUID of the source to update.
        source: Update payload (only provided fields are changed).
        db: SQLAlchemy session.

    Returns:
        The updated source.
    """
    return source_service.update_source(db, source_id, source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> None:
    """Delete a source by ID.

    Args:
        source_id: UUID of the source to delete.
        db: SQLAlchemy session.
    """
    source_service.delete_source(db, source_id)
