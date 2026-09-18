"""Base class and shared data structures for ISP modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from fast_openisp.config import BayerPattern, ModuleParams


class PipelineError(RuntimeError):
    """Raised when a module cannot process the current data."""


@dataclass(frozen=True)
class SaturationValues:
    """Maximum pixel values in the raw, HDR (after BLC) and SDR (after gamma) domains."""

    raw: int
    hdr: int
    sdr: int = 255


@dataclass(frozen=True)
class Context:
    """Per-run information shared by all modules."""

    bayer_pattern: BayerPattern
    bit_depth: int
    saturation: SaturationValues
    preview_factor: int = 1


@dataclass
class PipelineData:
    """Data flowing through the pipeline. Modules modify it in place."""

    bayer: np.ndarray
    rgb_image: np.ndarray | None = None
    y_image: np.ndarray | None = None
    cbcr_image: np.ndarray | None = None
    edge_map: np.ndarray | None = None
    awb_gains: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    """Effective white-balance gains (R, Gr, Gb, B) applied by AWB in this run."""
    extras: dict[str, object] = field(default_factory=dict)

    def require_rgb(self) -> np.ndarray:
        if self.rgb_image is None:
            raise PipelineError("RGB image is unavailable (is CFA enabled?)")
        return self.rgb_image

    def require_y(self) -> np.ndarray:
        if self.y_image is None:
            raise PipelineError("Luma image is unavailable (is CSC enabled?)")
        return self.y_image

    def require_cbcr(self) -> np.ndarray:
        if self.cbcr_image is None:
            raise PipelineError("Chroma image is unavailable (is CSC enabled?)")
        return self.cbcr_image

    def require_edge_map(self) -> np.ndarray:
        if self.edge_map is None:
            raise PipelineError("Edge map is unavailable (is EEH enabled?)")
        return self.edge_map


def to_fixed(value: float, scale: int) -> int:
    """Convert a real-valued parameter to the fixed-point integer used by the hardware model."""
    return round(value * scale)


class ISPModule[P: ModuleParams](ABC):
    """An ISP stage. Subclasses implement :meth:`execute`."""

    name: str = ""

    def __init__(self, params: P, ctx: Context) -> None:
        self.params = params
        self.ctx = ctx

    @abstractmethod
    def execute(self, data: PipelineData) -> None:
        """Process ``data`` in place."""
