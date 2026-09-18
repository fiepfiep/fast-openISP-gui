"""Auto white balance: per-channel gains, either manual or estimated with grey world."""

import numpy as np

from fast_openisp.config import AWBParams

from .base import ISPModule, PipelineData, to_fixed
from .helpers import reconstruct_bayer, split_bayer

#: Pixels at or above this fraction of the saturation value are ignored by grey world.
SATURATION_MARGIN = 0.98
MAX_GAIN = 8.0


def grey_world_gains(
    sub_arrays: list[np.ndarray], saturation: int
) -> tuple[float, float, float, float]:
    """Estimate (R, Gr, Gb, B) gains that equalise the R and B means to the green mean."""
    limit = SATURATION_MARGIN * saturation
    means = []
    for sub_array in sub_arrays:
        valid = sub_array[sub_array < limit]
        means.append(float(valid.mean()) if valid.size else float(sub_array.mean()))
    r_mean, gr_mean, gb_mean, b_mean = means
    g_mean = (gr_mean + gb_mean) / 2

    def gain(mean: float) -> float:
        return float(np.clip(g_mean / mean, 0.0, MAX_GAIN)) if mean > 0 else 1.0

    return gain(r_mean), 1.0, 1.0, gain(b_mean)


class AWB(ISPModule[AWBParams]):
    name = "awb"

    def execute(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.uint32)

        sub_arrays = split_bayer(bayer, self.ctx.bayer_pattern)
        if self.params.mode == "grey_world":
            gains = grey_world_gains(sub_arrays, self.ctx.saturation.hdr)
        else:
            p = self.params
            gains = (p.r_gain, p.gr_gain, p.gb_gain, p.b_gain)
        data.awb_gains = gains

        wb_sub_arrays = []
        for sub_array, gain in zip(sub_arrays, gains, strict=True):
            fixed_gain = np.uint32(to_fixed(gain, 1024))  # x1024
            wb_sub_arrays.append(np.right_shift(fixed_gain * sub_array, 10))
        wb_bayer = reconstruct_bayer(wb_sub_arrays, self.ctx.bayer_pattern)
        wb_bayer = np.clip(wb_bayer, 0, self.ctx.saturation.hdr)

        data.bayer = wb_bayer.astype(np.uint16)
