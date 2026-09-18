"""Black level compensation with optional R→Gr / B→Gb crosstalk correction."""

import numpy as np

from fast_openisp.config import BLCParams

from .base import Context, ISPModule, PipelineData, to_fixed
from .helpers import reconstruct_bayer, split_bayer


class BLC(ISPModule[BLCParams]):
    name = "blc"

    def __init__(self, params: BLCParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.alpha = np.array(to_fixed(params.alpha, 1024), dtype=np.int32)  # x1024
        self.beta = np.array(to_fixed(params.beta, 1024), dtype=np.int32)  # x1024

    def execute(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.int32)
        p = self.params

        r, gr, gb, b = split_bayer(bayer, self.ctx.bayer_pattern)
        r = np.clip(r - p.bl_r, 0, None)
        b = np.clip(b - p.bl_b, 0, None)
        gr -= p.bl_gr - np.right_shift(r * self.alpha, 10)
        gb -= p.bl_gb - np.right_shift(b * self.beta, 10)
        blc_bayer = reconstruct_bayer([r, gr, gb, b], self.ctx.bayer_pattern)

        data.bayer = np.clip(blc_bayer, 0, None).astype(np.uint16)
