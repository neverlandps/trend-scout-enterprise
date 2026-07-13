"""Source management service with validation and health tracking."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import Source
from trend_scout_enterprise.schemas.schemas import SourceCreate, SourceUpdate


VALID_SOURCE_TYPES = {"rss", "arxiv", "web_search", "custom_api"}


def validate_source_config(source_type: str, config: dict[str, Any]) -> None:
    """Validate source configuration based on source type.

    Args:
        source_type: The type of the source.
        config: The configuration dictionary.

    Raises:
        HTTPException: 400 if the source type is invalid or required config is missing.
    """
    if source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type: {source_type}. Must be one of {VALID_SOURCE_TYPES}",
        )
    if source_type in ("rss", "arxiv", "web_search", "custom_api"):
        if not config.get("url"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config 'url' is required for source type {source_type}",
            )


def create_source(db: Session, source: SourceCreate) -> Source:
    """Create a new signal source after validation.

    Args:
        db: SQLAlchemy session.
        source: Source creation payload.

    Returns:
        The created Source model instance.
    """
    validate_source_config(source.source_type, source.config)
    db_source = Source(
        id=str(__import__("uuid").uuid4()),
        **source.model_dump(),
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


def get_source(db: Session, source_id: str) -> Source:
    """Retrieve a source by ID.

    Args:
        db: SQLAlchemy session.
        source_id: UUID of the source.

    Returns:
        The Source model instance.

    Raises:
        HTTPException: 404 if the source does not exist.
    """
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return db_source


def list_sources(db: Session) -> list[Source]:
    """List all signal sources.

    Args:
        db: SQLAlchemy session.

    Returns:
        List of all Source model instances.
    """
    return db.query(Source).all()


def update_source(db: Session, source_id: str, source: SourceUpdate) -> Source:
    """Update an existing source.

    Args:
        db: SQLAlchemy session.
        source_id: UUID of the source to update.
        source: Update payload.

    Returns:
        The updated Source model instance.

    Raises:
        HTTPException: 404 if the source does not exist.
    """
    db_source = get_source(db, source_id)
    update_data = source.model_dump(exclude_unset=True)
    if "source_type" in update_data or "config" in update_data:
        new_type = update_data.get("source_type", db_source.source_type)
        new_config = update_data.get("config", db_source.config)
        validate_source_config(new_type, new_config)
    for field, value in update_data.items():
        setattr(db_source, field, value)
    db.commit()
    db.refresh(db_source)
    return db_source


def delete_source(db: Session, source_id: str) -> None:
    """Delete a source by ID.

    Args:
        db: SQLAlchemy session.
        source_id: UUID of the source to delete.

    Raises:
        HTTPException: 404 if the source does not exist.
    """
    db_source = get_source(db, source_id)
    db.delete(db_source)
    db.commit()


def update_source_health(
    db: Session,
    source_id: str,
    health_status: str,
    last_failure_reason: str | None = None,
) -> Source:
    """Update the health status of a source.

    Args:
        db: SQLAlchemy session.
        source_id: UUID of the source.
        health_status: New health status string.
        last_failure_reason: Optional failure reason text.

    Returns:
        The updated Source model instance.
    """
    db_source = get_source(db, source_id)
    db_source.health_status = health_status
    if last_failure_reason is not None:
        db_source.last_failure_reason = last_failure_reason
    db.commit()
    db.refresh(db_source)
    return db_source
