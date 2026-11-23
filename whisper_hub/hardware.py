"""Best-effort hardware detection for the first-run wizard."""

from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import catalog

logger = logging.getLogger(__name__)


def total_ram_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                kib = int(line.split()[1])
                return round(kib / 1024 / 1024, 1)
    except (OSError, ValueError):
        pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round(pages * page_size / 1024**3, 1)
    except (ValueError, OSError, AttributeError):
        return None


def _nvidia_smi() -> list[dict[str, Any]]:
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    gpus: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            vram_mb = int(float(parts[1]))
        except ValueError:
            vram_mb = 0
        gpus.append({"name": parts[0], "vram_gb": round(vram_mb / 1024, 1) if vram_mb else None})
    return gpus


def cuda_device_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def _torch_gpus() -> list[dict[str, Any]]:
    try:
        import torch

        if not torch.cuda.is_available():
            return []
        gpus = []
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            gpus.append(
                {
                    "name": torch.cuda.get_device_name(index),
                    "vram_gb": round(properties.total_memory / 1024**3, 1),
                }
            )
        return gpus
    except Exception:
        return []


def moondream_available() -> bool:
    return importlib.util.find_spec("moondream") is not None


def detect_hardware() -> dict[str, Any]:
    cpu_cores = os.cpu_count() or 1
    ram_gb = total_ram_gb()
    gpus = _nvidia_smi()
    cuda_devices = cuda_device_count()
    if not gpus and cuda_devices:
        gpus = _torch_gpus() or [{"name": "CUDA GPU", "vram_gb": None}]
    vram_gb = max((gpu["vram_gb"] or 0 for gpu in gpus), default=0) or None
    recommended = catalog.recommend(vram_gb, ram_gb, cpu_cores)
    return {
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "cuda_devices": max(cuda_devices, len(gpus)),
        "gpus": gpus,
        "has_cuda": bool(cuda_devices or gpus),
        "vram_gb": vram_gb,
        "moondream": moondream_available(),
        "recommended_model": recommended,
        "recommended_translate_model": catalog.recommend_translation(recommended, vram_gb),
        "recommended_engine": "whisper",
    }
