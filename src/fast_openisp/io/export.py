"""Writers for PNG and JPEG output."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

__all__ = ["EXPORT_EXTENSIONS", "ExportError", "encode_image", "save_image"]

EXPORT_EXTENSIONS = (".png", ".jpg", ".jpeg")


class ExportError(ValueError):
    """Raised when an image cannot be written."""


def encode_image(image: np.ndarray, suffix: str, *, jpeg_quality: int = 95) -> bytes:
    """Encode an RGB (or greyscale) uint8 image as PNG or JPEG bytes."""
    suffix = suffix.lower()
    if image.dtype != np.uint8:
        raise ExportError(f"Expected a uint8 image, got {image.dtype}")
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if image.ndim == 3 else image

    if suffix == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
    elif suffix in (".jpg", ".jpeg"):
        quality = max(1, min(100, jpeg_quality))
        params = [
            cv2.IMWRITE_JPEG_QUALITY,
            quality,
            cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
            cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
        ]
    else:
        raise ExportError(f"Unsupported export format {suffix!r} (use .png or .jpg)")

    ok, buffer = cv2.imencode(suffix, bgr, params)
    if not ok:
        raise ExportError(f"Encoding {suffix} failed")
    return buffer.tobytes()


def save_image(image: np.ndarray, path: str | Path, *, jpeg_quality: int = 95) -> Path:
    """Write ``image`` to ``path``; the format follows the file extension.

    Uses ``imencode`` + ``write_bytes`` so non-ASCII Windows paths work.
    """
    file = Path(path)
    data = encode_image(image, file.suffix, jpeg_quality=jpeg_quality)
    try:
        file.write_bytes(data)
    except OSError as error:
        raise ExportError(f"Cannot write {file}: {error}") from error
    return file
