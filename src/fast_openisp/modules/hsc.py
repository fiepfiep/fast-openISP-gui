"""Hue rotation and saturation control in the CbCr plane."""

import numpy as np

from fast_openisp.config import HSCParams

from .base import Context, ISPModule, PipelineData, to_fixed


class HSC(ISPModule[HSCParams]):
    name = "hsc"

    def __init__(self, params: HSCParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        hue_offset = np.pi * params.hue_offset / 180
        self.sin_hue = (256 * np.sin(hue_offset)).astype(np.int32)  # x256
        self.cos_hue = (256 * np.cos(hue_offset)).astype(np.int32)  # x256
        # x256
        self.saturation_gain = np.array(to_fixed(params.saturation_gain, 256), dtype=np.int32)

    def execute(self, data: PipelineData) -> None:
        cbcr_image = data.require_cbcr().astype(np.int32)

        cb_image, cr_image = np.split(cbcr_image, 2, axis=2)
        cb, cr = cb_image - 128, cr_image - 128

        hsc_cb_image = np.right_shift(self.cos_hue * cb - self.sin_hue * cr, 8)  # x256
        hsc_cb_image = np.right_shift(self.saturation_gain * hsc_cb_image, 8) + 128

        hsc_cr_image = np.right_shift(self.sin_hue * cb + self.cos_hue * cr, 8)  # x256
        hsc_cr_image = np.right_shift(self.saturation_gain * hsc_cr_image, 8) + 128

        hsc_cbcr_image = np.dstack([hsc_cb_image, hsc_cr_image])
        hsc_cbcr_image = np.clip(hsc_cbcr_image, 0, self.ctx.saturation.sdr)

        data.cbcr_image = hsc_cbcr_image.astype(np.uint8)
