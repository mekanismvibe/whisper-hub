"""faster-whisper inference, the detect → transcribe/translate policy, and idle unload."""

from __future__ import annotations

import gc
import logging
import threading
import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol

import numpy as np

from .config import Config
from .errors import DecodeError, EngineBusyError

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    detected_language: str
    language_probability: float | None
    task: str
    duration_s: float | None
    segments: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""


class TranscribeModel(Protocol):
    def transcribe(self, audio: Any, **kwargs: Any) -> tuple[Any, Any]: ...


class ModelSource(Protocol):
    def get_model(self, *, translate: bool) -> tuple[TranscribeModel, str]: ...

    def touch(self) -> None: ...

    @property
    def models_loaded(self) -> bool: ...


class SpeechModel(Protocol):
    def transcribe(self, **kwargs: Any) -> dict[str, Any]: ...


class SpeechSource(Protocol):
    def get_model(self) -> tuple[SpeechModel, str]: ...

    def touch(self) -> None: ...

    @property
    def models_loaded(self) -> bool: ...


def _segment_dict(segment: Any, index: int) -> dict[str, Any]:
    item = {
        "id": getattr(segment, "id", index),
        "start": float(getattr(segment, "start", 0.0)),
        "end": float(getattr(segment, "end", 0.0)),
        "text": getattr(segment, "text", ""),
    }
    tokens = getattr(segment, "tokens", None)
    if tokens is not None:
        item["tokens"] = list(tokens)
    for attr in ("seek", "temperature", "avg_logprob", "compression_ratio", "no_speech_prob"):
        value = getattr(segment, attr, None)
        if value is not None:
            item[attr] = value
    words = getattr(segment, "words", None)
    if words:
        item["words"] = [
            {
                "word": getattr(word, "word", ""),
                "start": getattr(word, "start", 0.0),
                "end": getattr(word, "end", 0.0),
                "probability": getattr(word, "probability", None),
            }
            for word in words
        ]
    return item


def _low_confidence_english(
    detected: str,
    language_probability: float | None,
    all_language_probs: Any,
    threshold: float,
) -> bool:
    """Short clips often get a wrong top language; keep English audio out of translate."""
    if detected == "en":
        return False
    probabilities = all_language_probs
    if not probabilities:
        return False
    by_language = dict(probabilities)
    top_probability = by_language.get(detected, language_probability or 0.0)
    english_probability = by_language.get("en", 0.0)
    return top_probability < threshold and english_probability >= 0.15


def _parakeet_segment_dict(segment: Any, index: int) -> dict[str, Any]:
    return {
        "id": index,
        "start": float(segment.get("start", 0.0)),
        "end": float(segment.get("end", 0.0)),
        "text": str(segment.get("text", "")),
    }


def _is_multilingual(model: Any) -> bool:
    """English-only checkpoints (*.en, distil) cannot detect languages or translate."""
    return bool(getattr(getattr(model, "model", None), "is_multilingual", True))


def _decode_audio(data: bytes) -> np.ndarray:
    """Decode any audio container to 16 kHz mono float32, entirely in memory.

    Mirrors ``faster_whisper.audio.decode_audio`` (same s16 mono resampler and
    500k-sample FIFO grouping, so the samples are bit-identical) but collects the
    resampled int16 chunks directly. That skips upstream's BytesIO copy, its second
    float32 allocation and its trailing ``gc.collect()``, which costs tens of
    milliseconds once torch and the models are loaded.
    """
    import av

    resampler = av.audio.resampler.AudioResampler(
        format="s16", layout="mono", rate=16000
    )
    chunks: list[np.ndarray] = []

    def valid_frames(frames: Any) -> Any:
        iterator = iter(frames)
        while True:
            try:
                yield next(iterator)
            except StopIteration:
                break
            except av.error.InvalidDataError:
                continue

    def grouped(frames: Any, num_samples: int = 500_000) -> Any:
        fifo = av.audio.fifo.AudioFifo()
        for frame in frames:
            frame.pts = None  # Ignore timestamp checks, like upstream.
            fifo.write(frame)
            if fifo.samples >= num_samples:
                yield fifo.read()
        if fifo.samples > 0:
            yield fifo.read()

    with av.open(BytesIO(data), mode="r", metadata_errors="ignore") as container:
        for frame in grouped(valid_frames(container.decode(audio=0))):
            chunks.extend(
                resampled.to_ndarray().reshape(-1)
                for resampled in resampler.resample(frame)
            )
        # Flush the resampler so the tail samples are not dropped.
        chunks.extend(
            resampled.to_ndarray().reshape(-1)
            for resampled in resampler.resample(None)
        )
    samples = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int16)
    audio = samples.astype(np.float32)
    audio /= 32768.0
    return audio


def _detector(models: ModelSource) -> Any | None:
    """The model whose language head decides routing; None when no model can detect."""
    model, _ = models.get_model(translate=False)
    if _is_multilingual(model):
        return model
    translator, _ = models.get_model(translate=True)
    return translator if _is_multilingual(translator) else None


def run_policy(
    models: ModelSource | None,
    audio: Any,
    *,
    prompt: str | None,
    language_hint: str | None,
    beam_size: int,
    honor_client_language: bool,
    lang_confidence: float = 0.5,
    speech: SpeechSource | None = None,
    translate_beam_size: int = 5,
    without_timestamps: bool = False,
    non_english: bool = False,
) -> TranscriptionResult:
    """Detect the language, then transcribe English or translate everything else.

    With ``speech`` (Parakeet), English is detected once with Whisper's language head
    and transcribed by ``speech``; Whisper is only asked for text when that fails.
    ``without_timestamps`` drops timestamp tokens from Whisper output; callers may only
    set it when the response does not need segment times.

    With ``non_english=False`` (the default) every clip is transcribed as English:
    no language detection runs, nothing is translated, and Parakeet needs no Whisper
    model at all.
    """
    if not non_english:
        return _run_english_only_policy(
            models,
            audio,
            prompt=prompt,
            beam_size=beam_size,
            speech=speech,
            without_timestamps=without_timestamps,
        )
    if models is None:
        raise RuntimeError("non-English support needs a Whisper model")
    if speech is not None:
        return _run_hybrid_policy(
            models,
            speech,
            audio,
            prompt=prompt,
            language_hint=language_hint,
            beam_size=beam_size,
            translate_beam_size=translate_beam_size,
            honor_client_language=honor_client_language,
            lang_confidence=lang_confidence,
            without_timestamps=without_timestamps,
        )
    model, model_name = models.get_model(translate=False)
    language = language_hint if honor_client_language else None
    if language is None and not _is_multilingual(model):
        # An English-only main model reports every clip as English; let the multilingual
        # translator detect so non-English speech is still translated.
        detector = _detector(models)
        if detector is not None:
            detected_hint, probability, _ = detector.detect_language(audio, vad_filter=True)
            detected_hint = (detected_hint or "en").lower()
            if detected_hint != "en":
                return _translate_only(
                    models, audio, detected=detected_hint, language_probability=probability,
                    prompt=prompt, translate_beam_size=translate_beam_size,
                    without_timestamps=without_timestamps,
                )
            language = "en"
    common: dict[str, Any] = {
        "vad_filter": True,
        "condition_on_previous_text": False,
        "initial_prompt": prompt or None,
        "without_timestamps": without_timestamps,
    }
    transcribe_options = {**common, "beam_size": beam_size}
    translate_options = {**common, "beam_size": translate_beam_size}
    segments, info = model.transcribe(
        audio, task="transcribe", language=language, **transcribe_options
    )
    detected = (getattr(info, "language", None) or "en").lower()
    language_probability = getattr(info, "language_probability", None)
    treat_as_english = _low_confidence_english(
        detected,
        language_probability,
        getattr(info, "all_language_probs", None),
        lang_confidence,
    )
    task = "transcribe"
    if detected == "en":
        consumed = list(segments)
        active_info = info
        active_model = model_name
    elif treat_as_english:
        # A short English clip misdetected as another language: decode it as English
        # instead of sending it through the translate task (which may mangle it).
        del segments
        segments, english_info = model.transcribe(
            audio, task="transcribe", language="en", **transcribe_options
        )
        consumed = list(segments)
        active_info = english_info
        active_model = model_name
    else:
        # Drop the English-decoding generator; only the translation is consumed.
        del segments
        translator, translator_name = models.get_model(translate=True)
        segments, translated_info = translator.transcribe(
            audio, task="translate", language=detected, **translate_options
        )
        consumed = list(segments)
        active_info = translated_info
        active_model = translator_name
        task = "translate"

    text = "".join(getattr(segment, "text", "") for segment in consumed).strip()
    return TranscriptionResult(
        text=text,
        detected_language=detected,
        language_probability=language_probability,
        task=task,
        duration_s=getattr(active_info, "duration", None),
        segments=[_segment_dict(segment, index) for index, segment in enumerate(consumed)],
        model=active_model,
    )


def _run_english_only_policy(
    models: ModelSource | None,
    audio: Any,
    *,
    prompt: str | None,
    beam_size: int,
    speech: SpeechSource | None,
    without_timestamps: bool,
) -> TranscriptionResult:
    """Transcribe every clip as English: no detection, no translation, no Whisper for Parakeet."""
    if speech is not None:
        try:
            speech_model, speech_name = speech.get_model()
            payload = speech_model.transcribe(
                audio=audio, sample_rate=16000, timestamps="segment"
            )
            text = str(payload.get("text") or "").strip()
            segments = payload.get("segments") or []
            duration = payload.get("duration_seconds")
            return TranscriptionResult(
                text=text,
                detected_language="en",
                language_probability=None,
                task="transcribe",
                duration_s=float(duration) if duration is not None else _audio_duration(audio),
                segments=[
                    _parakeet_segment_dict(segment, index)
                    for index, segment in enumerate(segments)
                ],
                model=speech_name,
            )
        except Exception as exc:
            # Never log the audio or any transcript text: the exception type is enough.
            logger.warning("parakeet failed (%s)", type(exc).__name__)
            if models is None:
                raise
    if models is None:
        raise RuntimeError("no speech model is configured")
    model, model_name = models.get_model(translate=False)
    segments, info = model.transcribe(
        audio,
        task="transcribe",
        language="en",
        vad_filter=True,
        beam_size=beam_size,
        condition_on_previous_text=False,
        initial_prompt=prompt or None,
        without_timestamps=without_timestamps,
    )
    consumed = list(segments)
    return TranscriptionResult(
        text="".join(getattr(segment, "text", "") for segment in consumed).strip(),
        detected_language="en",
        language_probability=getattr(info, "language_probability", None),
        task="transcribe",
        duration_s=getattr(info, "duration", None),
        segments=[_segment_dict(segment, index) for index, segment in enumerate(consumed)],
        model=model_name,
    )


def _translate_only(
    models: ModelSource,
    audio: Any,
    *,
    detected: str,
    language_probability: float | None,
    prompt: str | None,
    translate_beam_size: int,
    without_timestamps: bool,
) -> TranscriptionResult:
    translator, translator_name = models.get_model(translate=True)
    segments, info = translator.transcribe(
        audio, task="translate", language=detected, vad_filter=True,
        beam_size=translate_beam_size, condition_on_previous_text=False,
        initial_prompt=prompt or None, without_timestamps=without_timestamps,
    )
    consumed = list(segments)
    return TranscriptionResult(
        text="".join(getattr(segment, "text", "") for segment in consumed).strip(),
        detected_language=detected,
        language_probability=language_probability,
        task="translate",
        duration_s=getattr(info, "duration", None),
        segments=[_segment_dict(segment, index) for index, segment in enumerate(consumed)],
        model=translator_name,
    )


def _audio_duration(audio: Any) -> float | None:
    try:
        return float(len(audio)) / 16000
    except TypeError:
        return None


def _run_hybrid_policy(
    models: ModelSource,
    speech: SpeechSource,
    audio: Any,
    *,
    prompt: str | None,
    language_hint: str | None,
    beam_size: int,
    translate_beam_size: int,
    honor_client_language: bool,
    lang_confidence: float,
    without_timestamps: bool,
) -> TranscriptionResult:
    """Whisper detects (and translates), Parakeet transcribes English without decoding it twice."""
    common: dict[str, Any] = {
        "vad_filter": True,
        "condition_on_previous_text": False,
        "initial_prompt": prompt or None,
        "without_timestamps": without_timestamps,
    }
    transcribe_options = {**common, "beam_size": beam_size}
    translate_options = {**common, "beam_size": translate_beam_size}
    model, model_name = models.get_model(translate=False)
    if language_hint and honor_client_language:
        detected = language_hint.lower()
        language_probability: float | None = 1.0
        english = detected == "en"
    elif (detector := _detector(models)) is None:
        # Only English-only models are configured: everything is English by definition.
        detected, language_probability, english = "en", None, True
    else:
        detected, language_probability, all_language_probs = detector.detect_language(
            audio, vad_filter=True
        )
        detected = (detected or "en").lower()
        english = detected == "en" or _low_confidence_english(
            detected, language_probability, all_language_probs, lang_confidence
        )

    if english:
        try:
            speech_model, speech_name = speech.get_model()
            payload = speech_model.transcribe(
                audio=audio, sample_rate=16000, timestamps="segment"
            )
            text = str(payload.get("text") or "").strip()
            segments = payload.get("segments") or []
            duration = payload.get("duration_seconds")
            return TranscriptionResult(
                text=text,
                detected_language=detected,
                language_probability=language_probability,
                task="transcribe",
                duration_s=float(duration) if duration is not None else _audio_duration(audio),
                segments=[
                    _parakeet_segment_dict(segment, index)
                    for index, segment in enumerate(segments)
                ],
                model=speech_name,
            )
        except Exception as exc:
            # Never log the audio or any transcript text: the exception type is enough.
            logger.warning(
                "parakeet failed (%s); falling back to whisper for this request",
                type(exc).__name__,
            )
        segments, info = model.transcribe(
            audio, task="transcribe", language="en", **transcribe_options
        )
        consumed = list(segments)
        text = "".join(getattr(segment, "text", "") for segment in consumed).strip()
        return TranscriptionResult(
            text=text,
            detected_language=detected,
            language_probability=language_probability,
            task="transcribe",
            duration_s=getattr(info, "duration", None),
            segments=[_segment_dict(segment, index) for index, segment in enumerate(consumed)],
            model=model_name,
        )

    translator, translator_name = models.get_model(translate=True)
    segments, info = translator.transcribe(
        audio, task="translate", language=detected, **translate_options
    )
    consumed = list(segments)
    text = "".join(getattr(segment, "text", "") for segment in consumed).strip()
    return TranscriptionResult(
        text=text,
        detected_language=detected,
        language_probability=language_probability,
        task="translate",
        duration_s=getattr(info, "duration", None),
        segments=[_segment_dict(segment, index) for index, segment in enumerate(consumed)],
        model=translator_name,
    )


def cuda_usable() -> bool:
    """True when device=auto would pick the GPU."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0 and _cuda_runtime_available()
    except Exception:
        return False


def _cuda_runtime_available() -> bool:
    """CTranslate2 dlopens cuBLAS 12 and cuDNN 9 at first use; a GPU alone is not enough."""
    import ctypes
    import sys

    if not sys.platform.startswith("linux"):
        return True  # DLL names differ elsewhere; let CTranslate2 report problems itself
    for soname in ("libcublas.so.12", "libcudnn.so.9"):
        try:
            ctypes.CDLL(soname)
        except OSError:
            return False
    return True


def _warmup_whisper(model: Any, *, detect: bool = True) -> None:
    """Run one silent decode so the first real request does not pay the kernel warm-up.

    ``detect=False`` skips the language head entirely when the hub is English-only.
    """
    try:
        silence = np.zeros(16000 * 30, dtype=np.float32)
        if detect and _is_multilingual(model):
            model.detect_language(silence, vad_filter=False)
        # dictation is short: one second exercises the tokenizer/decoder too.
        transcribe_options: dict[str, Any] = {"beam_size": 1}
        if not detect:
            # Force English so the decoder does not run its own language detection.
            transcribe_options["language"] = "en"
        segments, _ = model.transcribe(silence[:16000], **transcribe_options)
        list(segments)
    except Exception as exc:
        logger.warning(
            "whisper warm-up failed (%s); the first request may be slower",
            type(exc).__name__,
        )


def _warmup_parakeet(model: Any) -> None:
    try:
        silence = np.zeros(16000 * 30, dtype=np.float32)
        model.transcribe(audio=silence, sample_rate=16000, timestamps="none")
    except Exception as exc:
        logger.warning(
            "parakeet warm-up failed (%s); the first request may be slower",
            type(exc).__name__,
        )


class WhisperModels:
    """Lazily load one or two CTranslate2 Whisper models and unload them on demand."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._primary: TranscribeModel | None = None
        self._translator: TranscribeModel | None = None
        self._primary_name = config.model
        self._translator_name = config.translate_model_name
        self._last_used = time.monotonic()
        self._device = self._resolve_device()
        self._compute_type = self._resolve_compute_type()

    def _resolve_device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                if _cuda_runtime_available():
                    return "cuda"
                logger.warning(
                    "A CUDA GPU is present but cuBLAS 12 / cuDNN 9 are missing; using the CPU. "
                    "Install them with 'uv sync --extra cuda' (or the :cuda image) to use the GPU."
                )
        except Exception:  # pragma: no cover - optional CUDA support
            logger.debug("CUDA detection failed; using CPU", exc_info=True)
        return "cpu"

    def _resolve_compute_type(self) -> str:
        if self.config.compute_type != "auto":
            return self.config.compute_type
        return "int8_float16" if self._device == "cuda" else "int8"

    @property
    def device(self) -> str:
        return self._device

    @property
    def compute_type(self) -> str:
        return self._compute_type

    @property
    def models_loaded(self) -> bool:
        return self._primary is not None

    @property
    def loaded_models(self) -> list[str]:
        names: list[str] = []
        if self._primary is not None:
            names.append(self._primary_name)
        if self._translator is not None and self._translator_name not in names:
            names.append(self._translator_name)
        return names

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_used

    def touch(self) -> None:
        self._last_used = time.monotonic()

    def _load(self, name: str) -> TranscribeModel:
        from faster_whisper import WhisperModel

        logger.info(
            "loading whisper model=%s device=%s compute_type=%s",
            name,
            self._device,
            self._compute_type,
        )
        started = time.monotonic()
        model = WhisperModel(
            name,
            device=self._device,
            compute_type=self._compute_type,
            cpu_threads=self.config.cpu_threads,
        )
        _warmup_whisper(model, detect=self.config.non_english)
        logger.info("loaded whisper model=%s in %.1fs", name, time.monotonic() - started)
        return model

    def get_model(self, *, translate: bool) -> tuple[TranscribeModel, str]:
        if translate and not self.config.non_english:
            raise RuntimeError("non-English support is disabled")
        with self._lock:
            self._last_used = time.monotonic()
            if translate and self._translator_name != self._primary_name:
                if self._translator is None:
                    self._translator = self._load(self._translator_name)
                return self._translator, self._translator_name
            if self._primary is None:
                self._primary = self._load(self._primary_name)
            if translate:
                # Same model for both roles.
                return self._primary, self._primary_name
            return self._primary, self._primary_name

    def load(self) -> None:
        self.get_model(translate=False)
        # English-only mode never translates, so the translation model stays unloaded.
        if self.config.non_english and self._translator_name != self._primary_name:
            self.get_model(translate=True)

    def unload(self) -> bool:
        with self._lock:
            had_models = self._primary is not None or self._translator is not None
            self._primary = None
            self._translator = None
        if had_models:
            gc.collect()
            logger.info("unloaded whisper models after idle timeout")
        return had_models


class ParakeetModels:
    """Lazily load Photon's Parakeet speech model and unload it on demand."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.model_name = config.parakeet_model
        self._lock = threading.RLock()
        self._model: SpeechModel | None = None
        self._last_used = time.monotonic()
        self._device = self._resolve_device()

    def _resolve_device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:  # pragma: no cover - optional GPU support
            logger.debug("CUDA detection failed for parakeet; using CPU", exc_info=True)
        return "cpu"

    @property
    def device(self) -> str:
        return self._device

    @property
    def models_loaded(self) -> bool:
        return self._model is not None

    @property
    def loaded_models(self) -> list[str]:
        return [self.model_name] if self._model is not None else []

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_used

    def touch(self) -> None:
        self._last_used = time.monotonic()

    def _load(self) -> SpeechModel:
        import moondream as md
        import torch

        logger.info("loading parakeet model=%s device=%s", self.model_name, self._device)
        started = time.monotonic()
        # Parakeet's single-pass runtime reserves a batch of 64 by default (~0.4 GB);
        # the hub is one request at a time (WHUB_MAX_CONCURRENCY), so a small batch
        # fits the GPU budget with no measured latency change. fp16 halves the resident
        # weights on CUDA; the CPU keeps the runtime's bf16 default because it has no
        # fast fp16 path.
        model = md.photon(
            self.model_name,
            device=self._device,
            single_pass_batch_capacity=2,
            dtype=torch.float16 if self._device == "cuda" else torch.bfloat16,
        )
        _warmup_parakeet(model)
        logger.info("loaded parakeet model=%s in %.1fs", self.model_name, time.monotonic() - started)
        return model

    def get_model(self) -> tuple[SpeechModel, str]:
        with self._lock:
            self._last_used = time.monotonic()
            if self._model is None:
                self._model = self._load()
            return self._model, self.model_name

    def load(self) -> None:
        self.get_model()

    def unload(self) -> bool:
        with self._lock:
            model = self._model
            self._model = None
            if model is None:
                return False
            try:
                model.close()
            except Exception:
                logger.warning("closing the parakeet model failed", exc_info=True)
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:  # pragma: no cover - optional GPU support
            pass
        logger.info("unloaded parakeet model after idle timeout")
        return True


class WhisperEngine:
    """Bytes in, English text out. All decoding stays in memory."""

    def __init__(
        self,
        config: Config,
        models: ModelSource | None = None,
        speech: SpeechSource | None = None,
    ) -> None:
        self.config = config
        if models is not None:
            self.models: ModelSource | None = models
        elif config.non_english or config.english_engine != "parakeet":
            self.models = WhisperModels(config)
        else:
            # English-only Parakeet needs no Whisper model: not even for detection.
            self.models = None
        if speech is None and config.english_engine == "parakeet":
            speech = ParakeetModels(config)
        self.speech = speech
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._retired = False

    @property
    def busy(self) -> bool:
        return self._inflight > 0

    @property
    def models_loaded(self) -> bool:
        return bool(
            (self.models is not None and self.models.models_loaded)
            or (self.speech is not None and self.speech.models_loaded)
        )

    @property
    def whisper_loaded(self) -> bool:
        return bool(self.models is not None and self.models.models_loaded)

    @property
    def parakeet_loaded(self) -> bool:
        return bool(self.speech and self.speech.models_loaded)

    @property
    def loaded_models(self) -> list[str]:
        names: list[str] = []
        for source in (self.models, self.speech):
            for name in getattr(source, "loaded_models", []) or []:
                if name not in names:
                    names.append(name)
        return names

    @property
    def idle_seconds(self) -> float:
        idle: list[float] = []
        if self.models is not None:
            idle.append(float(getattr(self.models, "idle_seconds", 0.0)))
        if self.speech is not None:
            idle.append(float(self.speech.idle_seconds))
        return min(idle) if idle else 0.0

    @property
    def device(self) -> str:
        return getattr(self.models, "device", None) or getattr(
            self.speech, "device", self.config.device
        )

    @property
    def compute_type(self) -> str | None:
        return getattr(self.models, "compute_type", None)

    @property
    def model_name(self) -> str:
        return self.config.model

    def transcribe_bytes(
        self,
        data: bytes,
        *,
        prompt: str | None = None,
        language: str | None = None,
        without_timestamps: bool = False,
    ) -> TranscriptionResult:
        with self._inflight_lock:
            self._inflight += 1
        try:
            return self._transcribe_bytes(
                data,
                prompt=prompt,
                language=language,
                without_timestamps=without_timestamps,
            )
        finally:
            if self.models is not None:
                self.models.touch()
            touch = getattr(self.speech, "touch", None)
            if callable(touch):
                touch()
            with self._inflight_lock:
                self._inflight -= 1
                release = self._retired and self._inflight == 0
            if release:
                self.unload()

    def _transcribe_bytes(
        self,
        data: bytes,
        *,
        prompt: str | None,
        language: str | None,
        without_timestamps: bool,
    ) -> TranscriptionResult:
        if self.models is not None:
            self.models.touch()
        try:
            audio = _decode_audio(data)
        except Exception as exc:
            raise DecodeError("could not decode audio") from exc
        finally:
            data = b""  # release the upload before inference
        if getattr(audio, "size", 0) == 0:
            raise DecodeError("audio stream is empty")
        try:
            return run_policy(
                self.models,
                audio,
                prompt=prompt,
                language_hint=language,
                beam_size=self.config.beam_size,
                translate_beam_size=self.config.translate_beam_size,
                honor_client_language=self.config.honor_client_language,
                lang_confidence=self.config.lang_confidence,
                speech=self.speech,
                without_timestamps=without_timestamps,
                non_english=self.config.non_english,
            )
        except DecodeError:
            raise
        except Exception as exc:
            raise EngineBusyError("transcription failed") from exc
        finally:
            del audio

    def retire(self) -> None:
        """Called after a hot swap: free this engine's models once its last request ends."""
        with self._inflight_lock:
            self._retired = True
            release = self._inflight == 0
        if release:
            self.unload()

    def unload(self) -> bool:
        unload = getattr(self.models, "unload", None)
        whisper_unloaded = bool(unload()) if callable(unload) else False
        parakeet_unloaded = self.speech.unload() if self.speech is not None else False
        return whisper_unloaded or parakeet_unloaded

    def load(self) -> None:
        load = getattr(self.models, "load", None)
        if callable(load):
            load()
        if self.speech is not None:
            self.speech.load()


class EngineProtocol(Protocol):
    @property
    def models_loaded(self) -> bool: ...

    def transcribe_bytes(
        self,
        data: bytes,
        *,
        prompt: str | None = None,
        language: str | None = None,
        without_timestamps: bool = False,
    ) -> TranscriptionResult: ...

    def unload(self) -> bool: ...

    def load(self) -> None: ...
