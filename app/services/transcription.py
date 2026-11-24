from faster_whisper import WhisperModel
from functools import lru_cache
from pathlib import Path
import json
import time


@lru_cache(maxsize=1)
def get_model(model_name="small"):
    return WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8"
    )


def transcribe_media(file_path: str, mode: str = "accurate"):
    start_time = time.perf_counter()

    models = {
        "fast": "small",
        "accurate": "large-v3"
    }

    if mode not in models:
        raise ValueError("Invalid transcription mode.")

    model_name = models[mode]
    model = get_model(model_name)

    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        multilingual=True,
        vad_filter=True,
        word_timestamps=True
    )

    transcript = []

    for index, segment in enumerate(segments):
        transcript.append({
            "id": index,
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "words": [
                {
                    "word": word.word.strip(),
                    "start": round(word.start, 2),
                    "end": round(word.end, 2),
                    "confidence": round(word.probability, 3)
                }
                for word in (segment.words or [])
            ]
        })

    result = {
        "model": model_name,
        "mode": mode,
        "language": info.language,
        "language_probability": round(
            info.language_probability, 3
        ),
        "duration": round(info.duration, 2),
        "processing_time": round(
            time.perf_counter() - start_time, 2
        ),
        "full_text": " ".join(
            segment["text"] for segment in transcript
        ),
        "segments": transcript
    }

    return result


def save_transcript(result: dict, project_id: str):
    directory = Path("storage/transcripts")
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{project_id}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    return output_path
