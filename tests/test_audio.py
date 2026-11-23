"""The in-memory decoder must match faster-whisper sample for sample."""

from __future__ import annotations

import io
import wave

import numpy as np
from faster_whisper import decode_audio

from whisper_hub.engine import _decode_audio


def _stereo_wav_bytes(seconds: float = 0.5, rate: int = 44100) -> bytes:
    frames = int(seconds * rate)
    time = np.arange(frames) / rate
    tone = 0.35 * np.sin(2 * np.pi * 440 * time)
    stereo = np.empty(frames * 2, dtype=np.int16)
    stereo[0::2] = np.round(tone * 0.9 * 32767).astype(np.int16)
    stereo[1::2] = np.round(tone * 0.4 * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(stereo.tobytes())
    return buffer.getvalue()


def test_decode_matches_upstream_bit_for_bit_on_stereo_wav():
    data = _stereo_wav_bytes()

    expected = decode_audio(io.BytesIO(data), sampling_rate=16000)
    actual = _decode_audio(data)

    assert actual.dtype == np.float32
    assert actual.shape == expected.shape == (8000,)
    assert actual.tobytes() == expected.tobytes()
