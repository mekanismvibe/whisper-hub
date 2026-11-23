"""Load the pip-installed CUDA wheels without LD_LIBRARY_PATH.

``uv sync --extra cuda`` installs cuBLAS and cuDNN as ordinary Python
packages. CTranslate2 dlopens them by name, so a service started without a
custom LD_LIBRARY_PATH fails on ``libcublas.so.12``. Preloading the shared
objects with ``RTLD_GLOBAL`` makes the wheels discoverable.
"""

from __future__ import annotations

import ctypes
import glob
import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PACKAGES = (
    ("nvidia.cublas", "libcublas*.so*"),
    ("nvidia.cudnn", "libcudnn*.so*"),
)


def preload_cuda_libraries() -> list[str]:
    """Best-effort preload; returns the library paths that loaded."""
    loaded: list[str] = []
    for package, pattern in _PACKAGES:
        try:
            module = importlib.import_module(package)
        except ImportError:
            continue
        if getattr(module, "__file__", None):
            root = Path(module.__file__).resolve().parent
        else:
            paths = list(getattr(module, "__path__", []))
            if not paths:
                continue
            root = Path(paths[0]).resolve()
        candidates = sorted(glob.glob(str(root / "**" / pattern), recursive=True))
        # One library per base name: the unversioned symlink if the wheel has
        # one, otherwise the shortest (most general) versioned name.
        chosen: dict[str, str] = {}
        for path in candidates:
            name = Path(path).name
            base = name.split(".so", 1)[0]
            current = chosen.get(base)
            if current is None:
                chosen[base] = path
                continue
            current_name = Path(current).name
            if (name.endswith(".so") and not current_name.endswith(".so")) or (
                name.endswith(".so") == current_name.endswith(".so") and len(name) < len(current_name)
            ):
                chosen[base] = path
        for path in sorted(chosen.values()):
            try:
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                loaded.append(path)
            except OSError:
                logger.debug("could not preload %s", path, exc_info=True)
    if loaded:
        logger.info("preloaded %d CUDA libraries from pip wheels", len(loaded))
    return loaded
