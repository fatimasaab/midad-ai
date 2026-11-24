from typing import Literal
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from app.services.transcription import (
    transcribe_media,
    save_transcript
)
import json
import logging

router = APIRouter(prefix="/api/media", tags=["Media"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("storage/uploads")
TRANSCRIPT_DIR = Path("storage/transcripts")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm",
    ".mp3", ".wav", ".m4a", ".aiff"
}

MAX_FILE_SIZE = 500 * 1024 * 1024


@router.post("/upload")
async def upload_media(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="Unsupported media format."
        )

    project_id = uuid4().hex
    file_path = UPLOAD_DIR / f"{project_id}{extension}"
    total_size = 0

    try:
        with open(file_path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File exceeds the 500 MB limit."
                    )

                output.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty."
            )

        return {
            "project_id": project_id,
            "filename": file.filename,
            "size_bytes": total_size,
            "status": "uploaded"
        }

    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    finally:
        await file.close()


@router.post("/{project_id}/transcribe")
async def transcribe(
    project_id: str,
    mode: Literal["fast", "accurate"] = "accurate"
):
    try:
        from uuid import UUID
        project_id = UUID(project_id).hex
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project ID."
        )

    files = list(UPLOAD_DIR.glob(f"{project_id}.*"))

    if not files:
        raise HTTPException(
            status_code=404,
            detail="Media file not found."
        )

    transcript_path = TRANSCRIPT_DIR / f"{project_id}.json"
    analysis_path = Path("storage/analysis") / f"{project_id}.json"

    if transcript_path.exists() or analysis_path.exists():
        raise HTTPException(
            status_code=409,
            detail="Existing transcript or analysis is protected."
        )

    try:
        result = await run_in_threadpool(
            transcribe_media,
            str(files[0]),
            mode
        )

        save_transcript(result, project_id)

        return {
            "project_id": project_id,
            "status": "transcribed",
            **result
        }

    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(
            status_code=500,
            detail="Unable to transcribe this media file."
        )


@router.get("/{project_id}/transcript")
def get_transcript(project_id: str):
    try:
        from uuid import UUID
        project_id = UUID(project_id).hex
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project ID."
        )

    path = TRANSCRIPT_DIR / f"{project_id}.json"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript not found."
        )

    with open(path, encoding="utf-8") as file:
        return json.load(file)


@router.get("/{project_id}/source")
def get_source(project_id: str):
    from uuid import UUID
    from fastapi.responses import FileResponse

    try:
        project_id = UUID(project_id).hex
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project ID."
        )

    files = list(UPLOAD_DIR.glob(f"{project_id}.*"))

    if not files:
        raise HTTPException(
            status_code=404,
            detail="Media file not found."
        )

    return FileResponse(files[0])


@router.get("/{project_id}/preview")
def get_preview(project_id: str):
    from uuid import UUID
    from fastapi.responses import FileResponse
    from app.services.preview import create_preview

    try:
        project_id = UUID(project_id).hex
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid project ID."
        )

    files = list(UPLOAD_DIR.glob(f"{project_id}.*"))

    if not files:
        raise HTTPException(
            status_code=404,
            detail="Media file not found."
        )

    try:
        preview_path = create_preview(
            files[0],
            project_id
        )

        return FileResponse(
            preview_path,
            media_type=(
                "video/mp4"
                if preview_path.suffix == ".mp4"
                else "audio/mpeg"
            )
        )

    except Exception:
        logger.exception("Preview generation failed")

        raise HTTPException(
            status_code=500,
            detail="Unable to generate media preview."
        )
