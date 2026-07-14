"""Schemas for SharePoint Online integration."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SharePointConnectionIn(BaseModel):
    """Request schema for configuring SharePoint connection."""

    name: str
    site_id: Optional[str] = None
    site_url: Optional[str] = None
    list_id: Optional[str] = None
    drive_id: Optional[str] = None
    tenant_id: str
    client_id: str
    client_secret: str
    is_enabled: bool = True
    is_default: bool = False


class SharePointConnectionUpdate(BaseModel):
    """Request schema for updating SharePoint connection."""

    name: Optional[str] = None
    site_id: Optional[str] = None
    site_url: Optional[str] = None
    list_id: Optional[str] = None
    drive_id: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class SharePointConnectionOut(BaseModel):
    """Response schema for SharePoint connection."""

    id: str
    name: str
    site_id: Optional[str]
    site_url: Optional[str]
    list_id: Optional[str]
    drive_id: Optional[str]
    tenant_id: str
    client_id: str
    is_enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SharePointHealthOut(BaseModel):
    """Response schema for SharePoint health check."""

    status: str
    message: Optional[str] = None


class SharePointUploadIn(BaseModel):
    """Request schema for uploading a report to SharePoint."""

    report_id: str
    connection_id: str


class SharePointUploadOut(BaseModel):
    """Response schema for SharePoint upload record."""

    id: str
    report_id: str
    sharepoint_connection_id: str
    web_url: Optional[str]
    item_id: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
