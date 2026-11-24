# Midad | مداد
### AI Editorial Studio for Islamic Educational Media

Midad is an independent, local-first AI editorial prototype
designed to help media teams transform long-form educational
content into shorter, context-preserving excerpts through
human-supervised AI workflows.

Developed by Fatima Saab as a creative technology portfolio
project inspired by the editorial needs of Yaqeen Institute.

## Features

- Local audio and video processing
- Multilingual English and Arabic transcription
- Fast and high-accuracy transcription modes
- Timestamped transcripts and word-level confidence scores
- Manual transcript correction with revision history
- AI-generated editorial clip recommendations
- Multilingual clip boundary validation
- Second-stage AI context evaluation
- Religious reference and transcription uncertainty flagging
- Editorial and scholarly review workflow
- Approval-gated media exports
- SRT and WebVTT subtitle generation
- Export metadata and SHA-256 media hashes

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Transcription | Faster Whisper |
| Transcription models | Whisper Small, Large V3 |
| Editorial intelligence | Qwen 2.5 7B |
| Local AI inference | Ollama |
| Media processing | FFmpeg |
| Storage | Local JSON and media files |

## Editorial Pipeline

Media Import
→ Multilingual Transcription
→ Human Transcript Correction
→ AI Candidate Generation
→ Deterministic Boundary Validation
→ AI Context Evaluation
→ Editorial Review
→ Scholarly Review When Required
→ Approved Media Export

## Pilot Evaluation

The prototype was evaluated locally on an Apple Silicon
MacBook Pro with 36 GB RAM using a 255.23-second episode
of Yaqeen Institute's Angels in Your Presence series.

Episode: When Allah Loves You

### Transcription Benchmark

| Model | Processing Time |
|---|---:|
| Whisper Small | 35.95 seconds |
| Whisper Small multilingual | 36.63 seconds |
| Whisper Large V3 multilingual | 224.38 seconds |

Large V3 produced noticeably better Arabic-script
transcription and religious terminology in the inspected
examples. Formal word error rate was not measured.

### Editorial Intelligence Benchmark

All three iterations used the same source transcript
and Qwen 2.5 7B model.

| Metric | V1 | V2 | V3 |
|---|---:|---:|---:|
| Processing time (seconds) | 18.28 | 15.61 | 17.76 |
| Suggested clips | 3 | 3 | 1 |
| Clips under 30 seconds | 1 | 2 | 0 |
| Clearly incomplete hadith endings | 1 | 1 | 0 |

The third iteration introduced stricter duration constraints,
multilingual boundary checks and a second AI context
validation pass.

The results demonstrate more conservative candidate selection
in this single-video pilot, rather than a general guarantee
of improved accuracy.

## Responsible AI

Midad prioritizes human judgment over automated publishing.

- AI recommendations are not scholarly verification.
- Low-confidence words are flagged for human inspection.
- Potential religious references require additional review.
- Clip recommendations retain their source transcript.
- Review decisions are recorded with timestamps.
- Exports are blocked until applicable approvals are recorded.
- No automatic publishing or synthetic religious depictions.
- Local processing avoids reliance on paid cloud AI APIs.

## Functional Testing

- Multilingual boundary validation: Passed
- Transcript correction and persistence: Passed
- Unapproved export request: HTTP 403
- Approved synthetic audio export: Passed
- Approved synthetic video export: HTTP 200
- Exported video playback: Passed
- SRT, WebVTT and metadata packaging: Passed

Export approval testing used simulated reviewer decisions
on synthetic media, not actual scholarly certification.

## Local Installation

Requirements:

- Python 3.11
- FFmpeg
- Ollama

On macOS:

    brew install python@3.11 ffmpeg ollama
    brew services start ollama
    ollama pull qwen2.5:7b

Create the Python environment:

    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Start the application:

    uvicorn app.main:app

Open http://127.0.0.1:8000

Whisper models are downloaded on first use.

## Current Limitations

- Editorial analysis currently supports recordings
  up to ten minutes.
- AI-generated descriptions may misrepresent subtle
  distinctions in the source material.
- Religious reference detection is heuristic.
- Reviewer identities are not authenticated.
- The evaluation is limited to a small pilot.
- Production deployment would require authentication,
  access control and stronger concurrency safeguards.

## Content and Independence

Midad is an independent portfolio prototype.
It is not affiliated with or endorsed by Yaqeen Institute.

Third-party media, transcripts and generated exports
are excluded from this repository. Users should only
process and distribute media they are authorized to use.

## Author

Fatima Saab

Computer Science | Artificial Intelligence | Creative Technology
