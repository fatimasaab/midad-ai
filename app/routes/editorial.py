from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import UUID
from starlette.concurrency import run_in_threadpool
from app.services.intelligence import analyze_transcript
import json
import logging

router = APIRouter(
    prefix="/api/editorial",
    tags=["Editorial Intelligence"]
)

logger = logging.getLogger(__name__)

TRANSCRIPT_DIR = Path("storage/transcripts")
ANALYSIS_DIR = Path("storage/analysis")

ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


def validate_project_id(project_id):
    try:
        return UUID(project_id).hex
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project ID."
        )


@router.post("/{project_id}/analyze")
async def analyze(project_id: str):
    project_id = validate_project_id(project_id)

    transcript_path = (
        TRANSCRIPT_DIR / f"{project_id}.json"
    )

    analysis_path = (
        ANALYSIS_DIR / f"{project_id}.json"
    )

    if not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generate a transcript first."
        )

    if analysis_path.exists():
        raise HTTPException(
            status_code=409,
            detail="Analysis already exists."
        )

    with open(transcript_path, encoding="utf-8") as file:
        transcript = json.load(file)

    try:
        result = await run_in_threadpool(
            analyze_transcript,
            transcript
        )

        from app.routes.review import review_lock

        with review_lock:
            if analysis_path.exists():
                raise HTTPException(
                    status_code=409,
                    detail="Analysis already exists."
                )

            with open(transcript_path, encoding="utf-8") as file:
                current_transcript = json.load(file)

            if current_transcript != transcript:
                raise HTTPException(
                    status_code=409,
                    detail="Transcript changed during analysis. Please retry."
                )

            result["project_id"] = project_id

            with open(
                analysis_path,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    result,
                    file,
                    ensure_ascii=False,
                    indent=2
                )

        return result

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception:
        logger.exception("Editorial analysis failed")

        raise HTTPException(
            status_code=500,
            detail="AI editorial analysis failed."
        )


@router.get("/{project_id}/analysis")
def get_analysis(project_id: str):
    project_id = validate_project_id(project_id)

    path = ANALYSIS_DIR / f"{project_id}.json"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Editorial analysis not found."
        )

    with open(path, encoding="utf-8") as file:
        return json.load(file)
