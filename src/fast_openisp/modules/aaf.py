"""Anti-aliasing filter: 3×3 weighted average per Bayer channel."""

import numpy as np

from fast_openisp.config import AAFParams

from .base import ISPModule, PipelineData
from .helpers import pad, reconstruct_bayer, shift_array, split_bayer


class AAF(ISPModule[AAFParams]):
    name = "aaf"

    def execute(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.uint32)

        padded_bayer = pad(bayer, pads=2)
        padded_sub_arrays = split_bayer(padded_bayer, self.ctx.bayer_pattern)

        aaf_sub_arrays = []
        for padded_array in padded_sub_arrays:
            shifted_arrays = shift_array(padded_array, window_size=3)
            aaf_sub_array = np.zeros_like(shifted_arrays[4])
            for i, shifted_array in enumerate(shifted_arrays):
                mul = 8 if i == 4 else 1
                aaf_sub_array += mul * shifted_array

            aaf_sub_arrays.append(np.right_shift(aaf_sub_array, 4))

        aaf_bayer = reconstruct_bayer(aaf_sub_arrays, self.ctx.bayer_pattern)

        data.bayer = aaf_bayer.astype(np.uint16)
