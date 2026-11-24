from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from uuid import uuid4
import subprocess
import zipfile
import hashlib
import json
import math

EXPORT_DIR = Path("storage/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def timestamp(seconds, separator=","):
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)

    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        f"{separator}{milliseconds:03d}"
    )


def generate_subtitles(transcript, clip):
    srt = []
    vtt = ["WEBVTT", ""]

    clip_start = clip["start"]
    clip_end = clip["end"]
    selected_ids = set(clip["source_segment_ids"])
    index = 1

    for segment in transcript["segments"]:
        if segment["id"] not in selected_ids:
            continue

        start = max(segment["start"], clip_start)
        end = min(segment["end"], clip_end)

        if end <= start:
            continue

        start -= clip_start
        end -= clip_start

        text = segment["text"].strip()

        if not text:
            continue

        srt.extend([
            str(index),
            f"{timestamp(start)} --> {timestamp(end)}",
            text,
            ""
        ])

        vtt.extend([
            f"{timestamp(start, '.')} --> {timestamp(end, '.')}",
            text.replace("&", "&amp;").replace(
                "<", "&lt;"
            ).replace(">", "&gt;"),
            ""
        ])

        index += 1

    return "\n".join(srt) + "\n", "\n".join(vtt) + "\n"


def file_hash(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def export_clip(source_path, transcript, clip, project_id):
    start = float(clip["start"])
    end = float(clip["end"])
    duration = end - start

    if (
        not math.isfinite(start)
        or not math.isfinite(end)
        or start < 0
        or duration <= 0
        or end > transcript["duration"] + 0.1
    ):
        raise ValueError("Invalid clip timestamps.")

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
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
    export_id = uuid4().hex

    with TemporaryDirectory(dir=EXPORT_DIR) as directory:
        folder = Path(directory)
        media_path = folder / f"clip{extension}"

        command = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", str(source_path),
            "-t", str(duration)
        ]

        if has_video:
            command += [
                "-map", "0:V:0",
                "-map", "0:a:0?",
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart"
            ]
        else:
            command += [
                "-vn",
                "-c:a", "libmp3lame",
                "-b:a", "192k"
            ]

        command.append(str(media_path))

        subprocess.run(
            command,
            capture_output=True,
            check=True,
            timeout=600
        )

        srt, vtt = generate_subtitles(transcript, clip)

        (folder / "subtitles.srt").write_text(
            srt, encoding="utf-8"
        )

        (folder / "subtitles.vtt").write_text(
            vtt, encoding="utf-8"
        )

        metadata = {
            "application": "Midad AI Editorial Studio",
            "project_id": project_id,
            "export_id": export_id,
            "exported_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "source_filename": source_path.name,
            "source_sha256": file_hash(source_path),
            "exported_media_sha256": file_hash(media_path),
            "language": transcript["language"],
            "transcription_model": transcript.get("model"),
            "transcript_revision": transcript.get("revision", 0),
            "correction_history": [
                correction
                for correction in transcript.get("correction_history", [])
                if correction["segment_id"] in clip["source_segment_ids"]
            ],
            "clip": clip,
            "notice": (
                "Independent editorial prototype. "
                "AI suggestions are not scholarly verification. "
                "Recorded reviewer identities are not authenticated."
            )
        }

        (folder / "metadata.json").write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        archive_path = (
            EXPORT_DIR / f"{project_id}_{export_id}.zip"
        )

        try:
            with zipfile.ZipFile(
                archive_path,
                "w",
                compression=zipfile.ZIP_DEFLATED
            ) as archive:

                for file in folder.iterdir():
                    archive.write(file, arcname=file.name)

        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

    return archive_path
