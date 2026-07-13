from fastapi import APIRouter

router = APIRouter()


@router.get("/reports")
def list_reports():
    return {"reports": []}


@router.post("/reports")
def create_report(request: dict):
    return {"report_id": "placeholder", "status": "generating"}


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    return {"report_id": report_id, "status": "ready"}


@router.get("/reports/{report_id}/download")
def download_report(report_id: str):
    return {"download_url": f"/outputs/{report_id}.pdf"}
