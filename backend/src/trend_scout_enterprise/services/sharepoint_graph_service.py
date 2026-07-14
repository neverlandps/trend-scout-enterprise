"""Microsoft Graph client credential helper for SharePoint Online."""

import requests
from typing import Optional

from trend_scout_enterprise.core.encryption import decrypt_value
from trend_scout_enterprise.models.sharepoint import SharePointConnection


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_access_token(connection: SharePointConnection) -> str:
    """Obtain a client-credentials access token for Microsoft Graph."""
    url = f"https://login.microsoftonline.com/{connection.tenant_id}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": connection.client_id,
        "client_secret": decrypt_value(connection.client_secret_encrypted),
        "scope": "https://graph.microsoft.com/.default",
    }
    response = requests.post(url, data=data, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


def graph_request(connection: SharePointConnection, path: str, method: str = "GET", json_body=None, params=None, binary=None):
    """Make an authenticated Microsoft Graph request."""
    token = get_access_token(connection)
    headers = {"Authorization": f"Bearer {token}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    url = f"{GRAPH_BASE}{path}"

    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        params=params,
        data=binary,
        timeout=60,
    )
    response.raise_for_status()
    return response


def list_sharepoint_items(connection: SharePointConnection) -> list[dict]:
    """List items from a SharePoint list."""
    site_id = connection.site_id or _resolve_site_id(connection)
    list_id = connection.list_id or _resolve_list_id(connection, site_id)
    path = f"/sites/{site_id}/lists/{list_id}/items"
    params = {"expand": "fields"}
    response = graph_request(connection, path, params=params)
    return response.json().get("value", [])


def _resolve_site_id(connection: SharePointConnection) -> str:
    if connection.site_url:
        hostname = connection.site_url.rstrip("/").split("/")[-2]
        site_path = connection.site_url.rstrip("/").split("/")[-1]
        path = f"/sites/{hostname}:{site_path}"
    else:
        raise ValueError("site_id or site_url must be provided")
    response = graph_request(connection, path)
    return response.json()["id"]


def _resolve_list_id(connection: SharePointConnection, site_id: str) -> str:
    if not connection.list_id:
        raise ValueError("list_id must be provided")
    return connection.list_id


def upload_report_to_sharepoint(connection: SharePointConnection, report_id: str, title: str, file_bytes: bytes, filename: str) -> dict:
    """Upload a report file to a SharePoint drive."""
    site_id = connection.site_id or _resolve_site_id(connection)
    drive_id = connection.drive_id or _resolve_default_drive_id(connection, site_id)
    path = f"/sites/{site_id}/drives/{drive_id}/root:/{filename}:/content"
    response = graph_request(connection, path, method="PUT", binary=file_bytes)
    return response.json()


def _resolve_default_drive_id(connection: SharePointConnection, site_id: str) -> str:
    response = graph_request(connection, f"/sites/{site_id}/drives")
    drives = response.json().get("value", [])
    if not drives:
        raise ValueError(f"No drives found for site {site_id}")
    return drives[0]["id"]


def check_sharepoint_health(connection: SharePointConnection) -> dict:
    """Validate Graph connection and return health status."""
    try:
        token = get_access_token(connection)
        response = requests.get(f"{GRAPH_BASE}/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        # /me is not available for client credentials; use /sites/root as a smoke test
        if response.status_code in (200, 401, 403, 404):
            response = requests.get(f"{GRAPH_BASE}/sites/root", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            response.raise_for_status()
        return {"status": "ok", "message": "Microsoft Graph connection successful"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
