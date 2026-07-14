"""SharePoint Online API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import resolve_current_identity
from trend_scout_enterprise.schemas.sharepoint import (
    SharePointConnectionIn,
    SharePointConnectionOut,
    SharePointConnectionUpdate,
    SharePointHealthOut,
    SharePointUploadIn,
    SharePointUploadOut,
)
from trend_scout_enterprise.services.sharepoint_service import SharePointService
from trend_scout_enterprise.models.models import Report


router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])


def _get_service(db: Session = Depends(get_db)) -> SharePointService:
    return SharePointService(db)


@router.post("/connections", response_model=SharePointConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: SharePointConnectionIn,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    return service.create_connection(payload.model_dump())


@router.get("/connections", response_model=list[SharePointConnectionOut])
def list_connections(
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    return service.list_connections()


@router.get("/connections/{connection_id}", response_model=SharePointConnectionOut)
def get_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    connection = service.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


@router.patch("/connections/{connection_id}", response_model=SharePointConnectionOut)
def update_connection(
    connection_id: str,
    payload: SharePointConnectionUpdate,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    connection = service.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return service.update_connection(connection, payload.model_dump(exclude_unset=True))


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    connection = service.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    service.delete_connection(connection)
    return None


@router.get("/connections/{connection_id}/health", response_model=SharePointHealthOut)
def check_health(
    connection_id: str,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    service = SharePointService(db)
    connection = service.get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return service.check_health(connection)


@router.post("/upload", response_model=SharePointUploadOut)
def upload_report(
    payload: SharePointUploadIn,
    db: Session = Depends(get_db),
    identity=Depends(resolve_current_identity),
):
    from pathlib import Path

    service = SharePointService(db)
    report = db.query(Report).filter_by(id=payload.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.file_path or not Path(report.file_path).exists():
        raise HTTPException(status_code=400, detail="Report file not found")

    file_bytes = Path(report.file_path).read_bytes()
    filename = Path(report.file_path).name
    return service.upload_report(payload.report_id, payload.connection_id, file_bytes, filename, report.title or "report")
