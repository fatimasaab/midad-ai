from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from uuid import UUID
from app.services.correction import correct_segment
from app.routes.review import review_lock
import json

router = APIRouter(
    prefix="/api/correction",
    tags=["Transcript Correction"]
)

TRANSCRIPT_DIR = Path("storage/transcripts")
ANALYSIS_DIR = Path("storage/analysis")


class CorrectionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


@router.patch("/{project_id}/segments/{segment_id}")
def update_segment(
    project_id: UUID,
    segment_id: int,
    request: CorrectionRequest
):
    project_id = project_id.hex

    transcript_path = TRANSCRIPT_DIR / f"{project_id}.json"
    analysis_path = ANALYSIS_DIR / f"{project_id}.json"

    with review_lock:

        if not transcript_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Transcript not found."
            )

        if analysis_path.exists():
            raise HTTPException(
                status_code=409,
                detail="Transcript is locked after editorial analysis."
            )

        with open(transcript_path, encoding="utf-8") as file:
            transcript = json.load(file)

        try:
            updated = correct_segment(
                transcript,
                segment_id,
                request.text
            )

        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )

        temporary_path = transcript_path.with_suffix(".tmp")

        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(
                updated,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary_path.replace(transcript_path)

        return updated
