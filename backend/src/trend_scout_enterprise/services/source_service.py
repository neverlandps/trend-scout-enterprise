"""Source management service with validation, encryption, and health tracking."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.encryption import decrypt_dict, encrypt_dict, mask_sensitive_config
from trend_scout_enterprise.models.models import ApiKey, Source
from trend_scout_enterprise.schemas.schemas import SourceCreate, SourceOut, SourceUpdate


VALID_SOURCE_TYPES = {"rss", "arxiv", "web_search", "custom_api", "sharepoint_list"}


_SUGGESTED_FIXES = {
    "rss": "Check the RSS feed URL is reachable and returns valid XML/Atom. Verify HTTPS certificate and any required auth headers.",
    "arxiv": "Verify the arXiv query syntax and network connectivity to export.arxiv.org.",
    "web_search": "Check the search API endpoint, query parameter, and API key/billing status.",
    "custom_api": "Check the API URL, method, headers, response_path, and field_mapping in the source config.",
    "sharepoint_list": "Check the SharePoint connection is enabled, the Graph API permissions are granted, and the list ID/site URL are correct.",
}


def _suggested_fix(source_type: str, error: str) -> str:
    """Return a human-readable fix suggestion for a failed source type."""
    base = _SUGGESTED_FIXES.get(source_type, "Review the source configuration and network connectivity.")
    return f"{base} Error: {error}"


def validate_source_config(source_type: str, config: dict[str, Any]) -> None:
    """Validate source configuration based on source type."""
    if source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type: {source_type}. Must be one of {VALID_SOURCE_TYPES}",
        )
    if source_type == "sharepoint_list":
        if not config.get("connection_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config 'connection_id' is required for sharepoint_list source type",
            )
        return
    if not config.get("url"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config 'url' is required for source type {source_type}",
        )


def create_source(db: Session, source: SourceCreate, owner: ApiKey, workspace_id: str) -> Source:
    """Create a new signal source after validation."""
    validate_source_config(source.source_type, source.config)
    db_source = Source(
        id=__import__("uuid").uuid4().hex,
        name=source.name,
        source_type=source.source_type,
        config_encrypted=encrypt_dict(source.config),
        category=source.category,
        tags=source.tags,
        enabled=source.enabled,
        refresh_interval_minutes=source.refresh_interval_minutes,
        owner_id=owner.id,
        workspace_id=workspace_id,
        health_status="unknown",
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


def get_source(db: Session, source_id: str, owner: ApiKey | None = None, workspace_id: str | None = None) -> Source:
    """Retrieve a source by ID, optionally scoped to an owner/workspace."""
    query = db.query(Source).filter(Source.id == source_id)
    if workspace_id is not None:
        query = query.filter(Source.workspace_id == workspace_id)
    elif owner is not None:
        query = query.filter(Source.owner_id == owner.id)
    db_source = query.first()
    if not db_source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return db_source


def list_sources(db: Session, owner: ApiKey | None = None, workspace_id: str | None = None) -> list[Source]:
    """List all signal sources, optionally scoped to an owner/workspace."""
    query = db.query(Source)
    if workspace_id is not None:
        query = query.filter(Source.workspace_id == workspace_id)
    elif owner is not None:
        query = query.filter(Source.owner_id == owner.id)
    return query.all()


def update_source(db: Session, source_id: str, source: SourceUpdate, owner: ApiKey | None = None, workspace_id: str | None = None) -> Source:
    """Update an existing source."""
    db_source = get_source(db, source_id, owner, workspace_id)
    update_data = source.model_dump(exclude_unset=True)
    if "source_type" in update_data or "config" in update_data:
        new_type = update_data.get("source_type", db_source.source_type)
        new_config = update_data.get("config")
        if new_config is not None:
            validate_source_config(new_type, new_config)
            db_source.config_encrypted = encrypt_dict(new_config)
            del update_data["config"]
        elif "source_type" in update_data:
            validate_source_config(new_type, decrypt_dict(db_source.config_encrypted))
    for field, value in update_data.items():
        setattr(db_source, field, value)
    db.commit()
    db.refresh(db_source)
    return db_source


def delete_source(db: Session, source_id: str, owner: ApiKey | None = None, workspace_id: str | None = None) -> None:
    """Delete a source by ID."""
    db_source = get_source(db, source_id, owner, workspace_id)
    db.delete(db_source)
    db.commit()


def update_source_health(
    db: Session,
    source_id: str,
    health_status: str,
    last_failure_reason: str | None = None,
    source_type: str = "custom_api",
) -> Source:
    """Update the health status of a source and provide a fix suggestion."""
    db_source = db.query(Source).filter(Source.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    db_source.health_status = health_status
    if last_failure_reason is not None:
        db_source.last_failure_reason = last_failure_reason
        db_source.suggested_fix = _suggested_fix(source_type, last_failure_reason)
    db.commit()
    db.refresh(db_source)
    return db_source


def source_to_schema(source: Source) -> SourceOut:
    """Convert a Source model to a SourceOut schema with masked config."""
    config = decrypt_dict(source.config_encrypted)
    return SourceOut(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        config=mask_sensitive_config(config),
        category=source.category,
        tags=source.tags,
        enabled=source.enabled,
        refresh_interval_minutes=source.refresh_interval_minutes,
        owner_id=source.owner_id,
        health_status=source.health_status,
        last_scan_at=source.last_scan_at,
        last_failure_reason=source.last_failure_reason,
        suggested_fix=source.suggested_fix,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def get_source_config(source: Source) -> dict[str, Any]:
    """Decrypt and return the full source configuration."""
    return decrypt_dict(source.config_encrypted)
