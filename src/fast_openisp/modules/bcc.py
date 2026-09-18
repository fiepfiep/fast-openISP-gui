"""Brightness and contrast control on the luma channel."""

import numpy as np

from fast_openisp.config import BCCParams

from .base import Context, ISPModule, PipelineData, to_fixed


class BCC(ISPModule[BCCParams]):
    name = "bcc"

    def __init__(self, params: BCCParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.brightness_offset = np.array(params.brightness_offset, dtype=np.int32)
        self.contrast_gain = np.array(to_fixed(params.contrast_gain, 256), dtype=np.int32)  # x256

    def execute(self, data: PipelineData) -> None:
        y_image = data.require_y().astype(np.int32)
        sdr = self.ctx.saturation.sdr

        bcc_y_image = np.clip(y_image + self.brightness_offset, 0, sdr)

        y_median = np.median(bcc_y_image).astype(np.int32)
        bcc_y_image = np.right_shift((bcc_y_image - y_median) * self.contrast_gain, 8) + y_median
        bcc_y_image = np.clip(bcc_y_image, 0, sdr)

        data.y_image = bcc_y_image.astype(np.uint8)
