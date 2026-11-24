from pathlib import Path
from threading import Lock
import subprocess
import json

PREVIEW_DIR = Path("storage/previews")
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

preview_lock = Lock()


def create_preview(source_path, project_id):
    with preview_lock:
        return generate_preview(source_path, project_id)


def generate_preview(source_path, project_id):
    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-of", "json",
            str(source_path)
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30
    )

    streams = json.loads(probe.stdout)["streams"]

    has_video = any(
        stream.get("codec_type") == "video"
        and not stream.get(
            "disposition", {}
        ).get("attached_pic", 0)
        for stream in streams
    )

    extension = ".mp4" if has_video else ".mp3"

    output_path = (
        PREVIEW_DIR / f"{project_id}{extension}"
    )

    if output_path.exists():
        return output_path

    temporary_path = (
        PREVIEW_DIR / f"{project_id}.tmp{extension}"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", str(source_path)
    ]

    if has_video:
        command += [
            "-map", "0:V:0",
            "-map", "0:a:0?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart"
        ]
    else:
        command += [
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "192k"
        ]

    command.append(str(temporary_path))

    try:
        subprocess.run(
            command,
            capture_output=True,
            check=True,
            timeout=600
        )

        temporary_path.replace(output_path)

    finally:
        temporary_path.unlink(missing_ok=True)

    return output_path
