"""Loaders for headerless raw, single-channel Bayer TIFF and DNG files."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from fast_openisp.config import BAYER_PATTERNS, BayerPattern

__all__ = [
    "IMAGE_EXTENSIONS",
    "LoadError",
    "RawImage",
    "TiffInfo",
    "bayer_pattern_from_cfa",
    "infer_bit_depth",
    "load_dng",
    "load_image",
    "load_raw",
    "load_tiff",
    "probe_tiff",
    "raw_size_candidates",
]

RAW_EXTENSIONS = (".raw",)
TIFF_EXTENSIONS = (".tif", ".tiff")
DNG_EXTENSIONS = (".dng",)
IMAGE_EXTENSIONS = RAW_EXTENSIONS + TIFF_EXTENSIONS + DNG_EXTENSIONS

ByteOrder = Literal["little", "big"]


class LoadError(ValueError):
    """Raised when an input file cannot be read as a Bayer image."""


@dataclass(frozen=True)
class RawImage:
    bayer: np.ndarray
    """(H, W) uint16 Bayer mosaic with even dimensions, LSB-aligned."""
    bit_depth: int
    bayer_pattern: BayerPattern
    source_path: Path
    black_level: tuple[int, int, int, int] | None = None
    """Per-channel (R, Gr, Gb, B) black level, when known from the file (DNG)."""
    as_shot_wb: tuple[float, float, float, float] | None = None
    """As-shot white-balance gains (R, Gr, Gb, B) normalised to green (DNG)."""

    @property
    def width(self) -> int:
        return int(self.bayer.shape[1])

    @property
    def height(self) -> int:
        return int(self.bayer.shape[0])


def _even_crop(array: np.ndarray) -> np.ndarray:
    height, width = array.shape[:2]
    return array[: height - height % 2, : width - width % 2]


def _check_pattern(pattern: str) -> BayerPattern:
    lowered = pattern.lower()
    for candidate in BAYER_PATTERNS:
        if candidate == lowered:
            return candidate
    raise LoadError(f"Unknown Bayer pattern {pattern!r}")


def infer_bit_depth(bayer: np.ndarray) -> int:
    """Smallest bit depth (8–16) that can hold the largest value of ``bayer``."""
    max_value = int(bayer.max()) if bayer.size else 0
    return min(16, max(8, math.ceil(math.log2(max_value + 1)) if max_value > 0 else 8))


def _msb_shift(bayer: np.ndarray) -> int:
    """Number of always-zero low bits (≥ 2 indicates MSB-aligned data)."""
    combined = int(np.bitwise_or.reduce(bayer, axis=None))
    if combined == 0:
        return 0
    return (combined & -combined).bit_length() - 1


def raw_size_candidates(file_size: int, bytes_per_pixel: int = 2) -> list[tuple[int, int]]:
    """Common (width, height) resolutions matching a headerless raw file size."""
    pixels, remainder = divmod(file_size, bytes_per_pixel)
    if remainder or pixels == 0:
        return []
    common = [
        (640, 480), (1280, 720), (1280, 800), (1280, 960), (1280, 1024), (1600, 1200),
        (1600, 1400), (1920, 1080), (1920, 1200), (2048, 1536), (2560, 1440), (2592, 1944),
        (3264, 2448), (3840, 2160), (4000, 3000), (4096, 2160), (4608, 3456), (1090, 1096),
    ]  # fmt: skip
    return [(w, h) for w, h in common if w * h == pixels]


def load_raw(
    path: str | Path,
    width: int,
    height: int,
    bit_depth: int,
    bayer_pattern: str,
    byte_order: ByteOrder = "little",
) -> RawImage:
    """Read a headerless 16-bit-per-pixel raw file."""
    file = Path(path)
    dtype = np.dtype("<u2" if byte_order == "little" else ">u2")
    expected = width * height * dtype.itemsize
    try:
        size = file.stat().st_size
    except OSError as error:
        raise LoadError(f"Cannot read {file.name}: {error}") from error
    if size != expected:
        raise LoadError(
            f"{file.name} is {size:,} bytes, but {width}×{height} 16-bit pixels need "
            f"{expected:,} bytes"
        )
    bayer = np.fromfile(file, dtype=dtype).reshape(height, width).astype(np.uint16)
    return RawImage(
        bayer=_even_crop(bayer),
        bit_depth=bit_depth,
        bayer_pattern=_check_pattern(bayer_pattern),
        source_path=file,
    )


@dataclass(frozen=True)
class TiffInfo:
    width: int
    height: int
    bit_depth: int
    """Bit depth inferred from the data (after undoing MSB alignment)."""
    msb_shift: int


def _read_tiff(path: Path) -> np.ndarray:
    import tifffile

    try:
        with tifffile.TiffFile(path) as tif:
            if len(tif.pages) != 1 and len(tif.series) > 1:
                raise LoadError(f"{path.name} contains multiple images; expected one Bayer frame")
            data = tif.asarray()
    except LoadError:
        raise
    except Exception as error:
        raise LoadError(f"Cannot read {path.name}: {error}") from error

    data = np.squeeze(data)
    if data.ndim != 2:
        raise LoadError(
            f"{path.name} has shape {data.shape}; expected a single-channel Bayer mosaic"
        )
    if not np.issubdtype(data.dtype, np.integer):
        raise LoadError(f"{path.name} has {data.dtype} samples; expected integer Bayer data")
    if data.dtype.itemsize > 2 and int(data.max()) > 65535:
        raise LoadError(f"{path.name} has values above 16 bit")
    return data.astype(np.uint16)


def probe_tiff(path: str | Path) -> TiffInfo:
    """Inspect a TIFF file without committing to a Bayer pattern."""
    data = _read_tiff(Path(path))
    shift = _msb_shift(data)
    shift = shift if shift >= 2 else 0
    depth = infer_bit_depth(data >> shift)
    return TiffInfo(width=data.shape[1], height=data.shape[0], bit_depth=depth, msb_shift=shift)


def load_tiff(path: str | Path, bayer_pattern: str, bit_depth: int | None = None) -> RawImage:
    """Read a single-channel Bayer TIFF.

    MSB-aligned data (all values a multiple of 4 or more) is shifted down. The bit depth is
    inferred from the data unless given.
    """
    file = Path(path)
    data = _read_tiff(file)
    shift = _msb_shift(data)
    if shift >= 2:
        data = data >> shift
    return RawImage(
        bayer=_even_crop(data),
        bit_depth=bit_depth if bit_depth is not None else infer_bit_depth(data),
        bayer_pattern=_check_pattern(bayer_pattern),
        source_path=file,
    )


def bayer_pattern_from_cfa(raw_pattern: Sequence[Sequence[int]], color_desc: str) -> BayerPattern:
    """Map a LibRaw 2×2 CFA pattern (indices into ``color_desc``, e.g. ``"RGBG"``) to a name."""
    try:
        letters = "".join(color_desc[raw_pattern[y][x]] for y in (0, 1) for x in (0, 1))
    except (IndexError, TypeError) as error:
        raise LoadError("Unsupported color filter array layout") from error
    return _check_pattern(letters.lower())


def load_dng(path: str | Path) -> RawImage:
    """Read a Bayer DNG (or other LibRaw-supported raw) with its metadata."""
    import rawpy

    file = Path(path)
    try:
        with rawpy.imread(str(file)) as raw:
            if raw.raw_type != rawpy.RawType.Flat or raw.num_colors != 3:
                raise LoadError(f"{file.name} is not a Bayer raw image")
            raw_pattern = raw.raw_pattern
            if raw_pattern is None or raw_pattern.shape != (2, 2):
                raise LoadError(f"{file.name} does not use a 2×2 Bayer color filter array")
            color_desc = raw.color_desc.decode("ascii")
            pattern = bayer_pattern_from_cfa(raw_pattern.tolist(), color_desc)

            bayer = np.array(raw.raw_image_visible, dtype=np.uint16)
            white_level = int(raw.white_level)
            per_channel = list(raw.black_level_per_channel)
            wb = list(raw.camera_whitebalance)
    except LoadError:
        raise
    except Exception as error:
        raise LoadError(f"Cannot read {file.name}: {error}") from error

    # Channel positions of R, Gr, Gb, B in the 2×2 cell, as color indices
    from fast_openisp.modules.helpers import get_bayer_indices

    color_index = [int(raw_pattern[y][x]) for x, y in get_bayer_indices(pattern)]
    black = tuple(int(per_channel[c]) for c in color_index)
    bit_depth = min(16, max(8, math.ceil(math.log2(white_level + 1))))

    as_shot: tuple[float, float, float, float] | None = None
    gains = [float(wb[c]) for c in color_index]
    green = (gains[1] + gains[2]) / 2 if gains[1] > 0 and gains[2] > 0 else max(gains[1], gains[2])
    if green > 0 and gains[0] > 0 and gains[3] > 0:
        as_shot = (gains[0] / green, 1.0, 1.0, gains[3] / green)

    return RawImage(
        bayer=_even_crop(bayer),
        bit_depth=bit_depth,
        bayer_pattern=pattern,
        source_path=file,
        black_level=(black[0], black[1], black[2], black[3]),
        as_shot_wb=as_shot,
    )


def load_image(
    path: str | Path,
    *,
    width: int,
    height: int,
    bit_depth: int | None,
    bayer_pattern: str,
    byte_order: ByteOrder = "little",
) -> RawImage:
    """Load any supported format. Metadata arguments are ignored where the file provides it."""
    file = Path(path)
    suffix = file.suffix.lower()
    if suffix in DNG_EXTENSIONS:
        return load_dng(file)
    if suffix in TIFF_EXTENSIONS:
        return load_tiff(file, bayer_pattern, bit_depth)
    if suffix in RAW_EXTENSIONS:
        if bit_depth is None:
            raise LoadError("A bit depth is required for headerless raw files")
        return load_raw(file, width, height, bit_depth, bayer_pattern, byte_order)
    raise LoadError(f"Unsupported file type {suffix!r}")
