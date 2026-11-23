"""The small Whisper model catalog used by the wizard, settings and docs.

Sizes are approximate download sizes for the CTranslate2 builds that
faster-whisper fetches from Hugging Face. Speed and quality are relative
(10 = fastest, 5 = best) so the UI can compare models without quoting
benchmark numbers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    download_mb: int
    ram_mb: int
    vram_mb: int
    speed: int
    quality: int
    can_translate: bool
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        id="tiny",
        label="Tiny",
        download_mb=75,
        ram_mb=400,
        vram_mb=350,
        speed=10,
        quality=1,
        can_translate=True,
        note="Fastest, least accurate. Good for smoke tests.",
    ),
    ModelInfo(
        id="base",
        label="Base",
        download_mb=145,
        ram_mb=600,
        vram_mb=500,
        speed=8,
        quality=2,
        can_translate=True,
        note="A good fit for CPU-only machines.",
    ),
    ModelInfo(
        id="small",
        label="Small",
        download_mb=485,
        ram_mb=1200,
        vram_mb=1000,
        speed=5,
        quality=3,
        can_translate=True,
        note="The usual balance of speed and accuracy.",
    ),
    ModelInfo(
        id="medium",
        label="Medium",
        download_mb=1500,
        ram_mb=2600,
        vram_mb=2300,
        speed=3,
        quality=4,
        can_translate=True,
        note="Better translation quality when the GPU has room.",
    ),
    ModelInfo(
        id="large-v3",
        label="Large v3",
        download_mb=3100,
        ram_mb=4700,
        vram_mb=4200,
        speed=1,
        quality=5,
        can_translate=True,
        note="Best accuracy; needs a capable GPU to feel fast.",
    ),
    ModelInfo(
        id="large-v3-turbo",
        label="Large v3 Turbo",
        download_mb=1600,
        ram_mb=2200,
        vram_mb=1900,
        speed=7,
        quality=4,
        can_translate=False,
        note="Fast and accurate, but it cannot translate. Pair it with a translation model.",
    ),
    ModelInfo(
        id="distil-large-v3",
        label="Distil Large v3",
        download_mb=1500,
        ram_mb=2000,
        vram_mb=1700,
        speed=6,
        quality=4,
        can_translate=False,
        note="English-only distillation; needs a separate translation model.",
    ),
    ModelInfo(
        id="distil-medium.en",
        label="Distil Medium (English)",
        download_mb=800,
        ram_mb=1200,
        vram_mb=1000,
        speed=7,
        quality=3,
        can_translate=False,
        note="English-only. It cannot translate other languages.",
    ),
)

MODEL_BY_ID: dict[str, ModelInfo] = {model.id: model for model in MODELS}


def model_info(name: str) -> ModelInfo | None:
    return MODEL_BY_ID.get((name or "").strip().lower())


def is_translatable(name: str) -> bool:
    """Unknown/custom model ids are assumed to be full Whisper builds."""
    info = model_info(name)
    return info.can_translate if info else True


def validate_models(main_model: str, translate_model: str) -> None:
    """Reject selections that would fail on non-English audio.

    ``translate_model`` may be empty (same model as the main one) but then the
    main model itself must be able to translate.
    """
    main = (main_model or "").strip()
    translate = (translate_model or "").strip()
    if not main:
        raise ValueError("Choose a main model.")
    if translate and not is_translatable(translate):
        raise ValueError(
            f"{translate} cannot translate. Pick a full Whisper model as the translation model."
        )
    if not translate and not is_translatable(main):
        raise ValueError(
            f"{main} cannot translate. Choose a translation model for non-English audio."
        )


def recommend(vram_gb: float | None, ram_gb: float | None, cpu_cores: int | None) -> str:
    """Suggest a main model from the detected hardware, generically."""
    if vram_gb:
        if vram_gb >= 10:
            return "medium"
        if vram_gb >= 6:
            return "medium"
        if vram_gb >= 3:
            return "small"
        return "base"
    cores = cpu_cores or 0
    if cores >= 8 and (ram_gb is None or ram_gb >= 8):
        return "small"
    return "base"


def recommend_translation(main_model: str, vram_gb: float | None) -> str:
    """Translation benefits from a full model; never recommend a turbo/distil."""
    if vram_gb and vram_gb >= 6:
        return "large-v3" if vram_gb >= 10 else "medium"
    if is_translatable(main_model):
        return ""
    return "small"


def catalog_payload() -> list[dict[str, Any]]:
    return [model.as_dict() for model in MODELS]
