"""OpenAI-compatible response renderers: json, text, verbose_json, srt, vtt."""

from __future__ import annotations

from typing import Any

from .engine import TranscriptionResult
from .languages import language_name

RESPONSE_FORMATS = {"json", "text", "verbose_json", "srt", "vtt"}


def _timestamp(seconds: float, *, separator: str) -> str:
    total_ms = max(0, round(float(seconds or 0) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(result: TranscriptionResult) -> str:
    segments = result.segments or [
        {"start": 0.0, "end": result.duration_s or 0.0, "text": result.text}
    ]
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _timestamp(segment.get("start", 0.0), separator=",")
        end = _timestamp(segment.get("end", 0.0), separator=",")
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(result: TranscriptionResult) -> str:
    segments = result.segments or [
        {"start": 0.0, "end": result.duration_s or 0.0, "text": result.text}
    ]
    blocks = ["WEBVTT\n"]
    for segment in segments:
        start = _timestamp(segment.get("start", 0.0), separator=".")
        end = _timestamp(segment.get("end", 0.0), separator=".")
        text = str(segment.get("text", "")).strip()
        blocks.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def verbose_json(result: TranscriptionResult) -> dict[str, Any]:
    return {
        "task": result.task,
        "language": language_name(result.detected_language),
        "duration": result.duration_s,
        "text": result.text,
        "segments": result.segments,
    }
