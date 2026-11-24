from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from threading import Lock
from app.routes.editorial import (
    validate_project_id,
    ANALYSIS_DIR
)
from app.services.review import apply_review
import json

router = APIRouter(
    prefix="/api/review",
    tags=["Editorial and Scholarly Review"]
)

review_lock = Lock()


class ReviewRequest(BaseModel):
    review_type: Literal["editorial", "scholarly"]
    decision: Literal["approved", "rejected"]
    reviewer: str = Field(min_length=1, max_length=100)
    notes: str = Field(min_length=1, max_length=2000)
    require_scholarly: bool = False


@router.post("/{project_id}/clips/{clip_id}")
def review_clip(
    project_id: str,
    clip_id: int,
    request: ReviewRequest
):
    project_id = validate_project_id(project_id)
    path = ANALYSIS_DIR / f"{project_id}.json"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Editorial analysis not found."
        )

    with review_lock:
        with open(path, encoding="utf-8") as file:
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

        try:
            updated_clip = apply_review(
                clip,
                request.review_type,
                request.decision,
                request.reviewer,
                request.notes,
                request.require_scholarly
            )

        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )

        temporary_path = path.with_suffix(".tmp")

        with open(
            temporary_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                analysis,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary_path.replace(path)

    return updated_clip
