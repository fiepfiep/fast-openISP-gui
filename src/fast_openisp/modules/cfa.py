"""Demosaicing (color filter array interpolation): bilinear or Malvar-He-Cutler."""

from collections.abc import Sequence

import numpy as np

from fast_openisp.config import CFAParams

from .base import Context, ISPModule, PipelineData
from .helpers import pad, reconstruct_bayer, shift_array, split_bayer

_ROTATE_TO_RGGB = {"rggb": 0, "bggr": 2, "grbg": 1, "gbrg": 3}
_ROTATE_FROM_RGGB = {"rggb": 0, "bggr": 2, "grbg": 3, "gbrg": 1}

# (indices into the 3×3 shifted neighbourhood, weights) of the Malvar kernels
_MALVAR_KERNELS: tuple[tuple[list[int], list[float]], ...] = (
    ([1, 3, 4, 5, 7], [-0.125, -0.125, 0.5, -0.125, -0.125]),
    ([1, 3, 4, 5, 7], [-0.1875, -0.1875, 0.75, -0.1875, -0.1875]),
    ([1, 3, 4, 5, 7], [0.0625, -0.125, 0.625, -0.125, 0.0625]),
    ([1, 3, 4, 5, 7], [-0.125, 0.0625, 0.625, 0.0625, -0.125]),
    ([3, 4], [0.25, 0.25]),
    ([1, 4], [0.25, 0.25]),
    ([4, 7], [0.25, 0.25]),
    ([4, 5], [0.25, 0.25]),
    ([4, 5], [0.5, 0.5]),
    ([1, 3], [0.5, 0.5]),
    ([1, 4], [0.5, 0.5]),
    ([4, 7], [0.5, 0.5]),
    ([3, 4], [0.5, 0.5]),
    ([0, 1, 3, 4], [0.25, 0.25, 0.25, 0.25]),
    ([4, 5, 7, 8], [0.25, 0.25, 0.25, 0.25]),
    ([1, 2, 4, 5], [-0.125, -0.125, -0.125, -0.125]),
    ([3, 4, 6, 7], [-0.125, -0.125, -0.125, -0.125]),
)


class CFA(ISPModule[CFAParams]):
    name = "cfa"

    def __init__(self, params: CFAParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        # x1024
        self.kernels = [
            (indices, [int(1024 * w) for w in weights]) for indices, weights in _MALVAR_KERNELS
        ]

    def rotate_to_rggb(self, array: np.ndarray) -> np.ndarray:
        return np.rot90(array, k=_ROTATE_TO_RGGB[self.ctx.bayer_pattern])

    def rotate_from_rggb(self, array: np.ndarray) -> np.ndarray:
        return np.rot90(array, k=_ROTATE_FROM_RGGB[self.ctx.bayer_pattern])

    def weighted_sum(self, arrays: Sequence[np.ndarray], kernel: int) -> np.ndarray:
        indices, weights = self.kernels[kernel]
        result = np.zeros_like(arrays[0])
        for i, w in zip(indices, weights, strict=True):
            result += w * arrays[i]
        return result

    def execute(self, data: PipelineData) -> None:
        if self.params.mode == "bilinear":
            self.execute_bilinear(data)
        else:
            self.execute_malvar(data)

    def _finish(self, data: PipelineData, planes: list[np.ndarray]) -> None:
        rgb_image = self.rotate_from_rggb(np.dstack(planes))
        rgb_image = np.clip(rgb_image, 0, self.ctx.saturation.hdr)
        data.rgb_image = rgb_image.astype(np.uint16)

    def execute_bilinear(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.int32)
        bayer = self.rotate_to_rggb(bayer)  # RGGB pattern

        r, gr, gb, b = split_bayer(bayer, bayer_pattern="rggb")
        height, width = r.shape

        # R-channel
        padded_r = pad(r, pads=(0, 1, 0, 1))
        r_right = padded_r[:height, 1 : 1 + width]
        r_bottom = padded_r[1 : 1 + height, :width]
        r_br = padded_r[1 : 1 + height, 1 : 1 + width]

        r_on_gr = np.right_shift(r + r_right, 1)
        r_on_gb = np.right_shift(r + r_bottom, 1)
        r_on_b = np.right_shift(r + r_right + r_bottom + r_br, 2)

        # G-channel
        padded_gr = pad(gr, pads=(0, 1, 1, 0))
        padded_gb = pad(gb, pads=(1, 0, 0, 1))
        gr_left = padded_gr[:height, :width]
        gr_bottom = padded_gr[1 : 1 + height, 1 : 1 + width]
        gb_top = padded_gb[:height, :width]
        gb_right = padded_gb[1 : 1 + height, 1 : 1 + width]

        g_on_r = np.right_shift(gr_left + gr + gb_top + gb, 2)
        g_on_b = np.right_shift(gr + gr_bottom + gb + gb_right, 2)

        # B-channel
        padded_b = pad(b, pads=(1, 0, 1, 0))
        b_top = padded_b[:height, 1 : 1 + width]
        b_left = padded_b[1 : 1 + height, :width]
        b_tl = padded_b[:height, :width]

        b_on_r = np.right_shift(b_tl + b_top + b_left + b, 2)
        b_on_gr = np.right_shift(b_top + b, 1)
        b_on_gb = np.right_shift(b_left + b, 1)

        self._finish(
            data,
            [
                reconstruct_bayer([r, r_on_gr, r_on_gb, r_on_b], bayer_pattern="rggb"),
                reconstruct_bayer([g_on_r, gr, gb, g_on_b], bayer_pattern="rggb"),
                reconstruct_bayer([b_on_r, b_on_gr, b_on_gb, b], bayer_pattern="rggb"),
            ],
        )

    def execute_malvar(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.int32)
        bayer = self.rotate_to_rggb(bayer)  # RGGB pattern

        r, gr, gb, b = split_bayer(bayer, bayer_pattern="rggb")

        padded_bayer = pad(bayer, pads=2)
        padded_r, padded_gr, padded_gb, padded_b = split_bayer(padded_bayer, bayer_pattern="rggb")

        s_r = shift_array(padded_r, window_size=3)
        s_gr = shift_array(padded_gr, window_size=3)
        s_gb = shift_array(padded_gb, window_size=3)
        s_b = shift_array(padded_b, window_size=3)
        ws = self.weighted_sum

        # ---------------- R-plane ----------------
        g_on_r = np.right_shift(ws(s_r, 0) + ws(s_gr, 4) + ws(s_gb, 5), 10)
        b_on_r = np.right_shift(ws(s_r, 1) + ws(s_b, 13), 10)

        # ---------------- Gr-plane ----------------
        r_on_gr = np.right_shift(ws(s_r, 8) + ws(s_gr, 2) + ws(s_gb, 15), 10)
        b_on_gr = np.right_shift(ws(s_b, 10) + ws(s_gr, 3) + ws(s_gb, 15), 10)

        # ---------------- Gb-plane ----------------
        r_on_gb = np.right_shift(ws(s_r, 11) + ws(s_gr, 16) + ws(s_gb, 3), 10)
        b_on_gb = np.right_shift(ws(s_b, 12) + ws(s_gr, 16) + ws(s_gb, 2), 10)

        # ---------------- B-plane ----------------
        r_on_b = np.right_shift(ws(s_r, 14) + ws(s_b, 1), 10)
        g_on_b = np.right_shift(ws(s_gr, 6) + ws(s_gb, 7) + ws(s_b, 0), 10)

        self._finish(
            data,
            [
                reconstruct_bayer([r, r_on_gr, r_on_gb, r_on_b], bayer_pattern="rggb"),
                reconstruct_bayer([g_on_r, gr, gb, g_on_b], bayer_pattern="rggb"),
                reconstruct_bayer([b_on_r, b_on_gr, b_on_gb, b], bayer_pattern="rggb"),
            ],
        )
