from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from app.routes.editorial import (
    validate_project_id,
    ANALYSIS_DIR
)
from app.routes.review import review_lock
from app.services.export import export_clip
from app.services.review import can_export
import json
import logging

router = APIRouter(
    prefix="/api/export",
    tags=["Approved Media Exports"]
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("storage/uploads")
TRANSCRIPT_DIR = Path("storage/transcripts")


@router.post("/{project_id}/clips/{clip_id}")
def generate_export(project_id: str, clip_id: int):

    project_id = validate_project_id(project_id)

    analysis_path = ANALYSIS_DIR / f"{project_id}.json"
    transcript_path = TRANSCRIPT_DIR / f"{project_id}.json"

    if not analysis_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Editorial analysis not found."
        )

    if not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript not found."
        )

    sources = list(
        UPLOAD_DIR.glob(f"{project_id}.*")
    )

    if not sources:
        raise HTTPException(
            status_code=404,
            detail="Original media not found."
        )

    with review_lock:

        with open(analysis_path, encoding="utf-8") as file:
            analysis = json.load(file)

        clip = next(
            (
                item for item in analysis["clips"]
                if item["id"] == clip_id
            ),
            None
        )

        if clip is None:
            raise HTTPException(
                status_code=404,
                detail="Clip not found."
            )

        if (
            clip.get("status") != "approved"
            or clip.get("editorial_status") != "approved"
            or clip.get("export_allowed") is not True
            or not can_export(clip)
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Export blocked. Required human "
                    "approvals have not been completed."
                )
            )

        with open(transcript_path, encoding="utf-8") as file:
            transcript = json.load(file)

        try:
            archive_path = export_clip(
                sources[0],
                transcript,
                clip,
                project_id
            )

        except Exception:
            logger.exception("Export generation failed")

            raise HTTPException(
                status_code=500,
                detail="Unable to generate export package."
            )

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"midad-clip-{clip_id}.zip"
    )
