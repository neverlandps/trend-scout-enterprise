"""Source management API endpoints using source_service."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import hash_api_key, verify_api_key
from trend_scout_enterprise.models.models import ApiKey
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


def _resolve_owner(x_api_key: str, db: Session) -> ApiKey:
    """Resolve a plaintext API key to an ApiKey entity."""
    key_hash = hash_api_key(x_api_key)
    owner = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    owner.last_used_at = __import__("datetime").datetime.utcnow()
    db.commit()
    db.refresh(owner)
    return owner


@router.get("/sources", response_model=SourceListOut)
def list_sources(
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> SourceListOut:
    """List all signal sources owned by the authenticated API key."""
    owner = _resolve_owner(x_api_key, db)
    sources = source_service.list_sources(db, owner)
    return SourceListOut(sources=[source_service.source_to_schema(s) for s in sources])


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    source: SourceCreate,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> SourceOut:
    """Create a new signal source."""
    owner = _resolve_owner(x_api_key, db)
    db_source = source_service.create_source(db, source, owner)
    return source_service.source_to_schema(db_source)


@router.get("/sources/scanner-types", response_model=ScannerTypeOut)
def scanner_types(
    _: str = Depends(verify_api_key),
) -> ScannerTypeOut:
    """Return the list of supported source/scanner types."""
    return ScannerTypeOut(scanner_types=list_scanner_types())


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(
    source_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> SourceOut:
    """Retrieve a single source by ID."""
    owner = _resolve_owner(x_api_key, db)
    db_source = source_service.get_source(db, source_id, owner)
    return source_service.source_to_schema(db_source)


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: str,
    source: SourceUpdate,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> SourceOut:
    """Update an existing source."""
    owner = _resolve_owner(x_api_key, db)
    db_source = source_service.update_source(db, source_id, source, owner)
    return source_service.source_to_schema(db_source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> None:
    """Delete a source by ID."""
    owner = _resolve_owner(x_api_key, db)
    source_service.delete_source(db, source_id, owner)


@router.get("/sources/{source_id}/health", response_model=SourceHealthOut)
def get_source_health(
    source_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> SourceHealthOut:
    """Retrieve the health status of a source."""
    owner = _resolve_owner(x_api_key, db)
    db_source = source_service.get_source(db, source_id, owner)
    return SourceHealthOut(
        source_id=db_source.id,
        health_status=db_source.health_status,
        last_scan_at=db_source.last_scan_at,
        last_failure_reason=db_source.last_failure_reason,
        suggested_fix=db_source.suggested_fix,
    )
