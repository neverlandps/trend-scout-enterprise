from fastapi import APIRouter

router = APIRouter()


@router.post("/scans")
def trigger_scan():
    return {"scan_id": "placeholder", "status": "queued"}


@router.get("/scans")
def list_scans():
    return {"scans": []}


@router.get("/scans/{scan_id}")
def get_scan(scan_id: str):
    return {"scan_id": scan_id, "status": "pending"}
