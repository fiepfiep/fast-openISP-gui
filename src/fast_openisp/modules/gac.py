"""Gamma correction: linear gain followed by a power-law LUT to 8 bit."""

import numpy as np

from fast_openisp.config import GACParams

from .base import Context, ISPModule, PipelineData, to_fixed


class GAC(ISPModule[GACParams]):
    name = "gac"

    def __init__(self, params: GACParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        hdr = ctx.saturation.hdr
        self.gain = np.array(to_fixed(params.gain, 256), dtype=np.uint32)  # x256
        x = np.arange(hdr + 1)
        lut = ((x / hdr) ** params.gamma) * ctx.saturation.sdr
        self.lut = lut.astype(np.uint8)

    def execute(self, data: PipelineData) -> None:
        rgb_image = data.require_rgb().astype(np.uint32)

        gac_rgb_image = np.right_shift(self.gain * rgb_image, 8)
        gac_rgb_image = np.clip(gac_rgb_image, 0, self.ctx.saturation.hdr)

        data.rgb_image = self.lut[gac_rgb_image]
