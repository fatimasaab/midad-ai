from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy
import json


def correct_segment(transcript, segment_id, text):

    updated = deepcopy(transcript)

    segment = next(
        (
            item for item in updated["segments"]
            if item["id"] == segment_id
        ),
        None
    )

    if segment is None:
        raise ValueError("Transcript segment not found.")

    text = text.strip()

    if not text:
        raise ValueError("Corrected text cannot be empty.")

    if text == segment["text"]:
        return updated

    if "original_text" not in segment:
        segment["original_text"] = segment["text"]
        segment["original_words"] = segment.get("words", [])

    updated.setdefault("correction_history", []).append({
        "segment_id": segment_id,
        "previous_text": segment["text"],
        "corrected_text": text,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    segment["text"] = text
    segment["words"] = []
    segment["manually_corrected"] = True

    updated["revision"] = updated.get("revision", 0) + 1

    updated["full_text"] = " ".join(
        item["text"] for item in updated["segments"]
    )

    return updated
