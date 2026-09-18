"""Color correction matrix (3×3 plus offset)."""

import numpy as np

from fast_openisp.config import CCMParams

from .base import Context, ISPModule, PipelineData, to_fixed


class CCM(ISPModule[CCMParams]):
    name = "ccm"

    def __init__(self, params: CCMParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        fixed = [[to_fixed(v, 1024) for v in row] for row in params.ccm]
        ccm = np.array(fixed, dtype=np.int32).T  # x1024, (4, 3) right-matrix
        self.matrix = ccm[:3, :]  # (3, 3) right-matrix
        self.bias = ccm[3, :].reshape(1, 1, 3)  # (1, 1, 3)

    def execute(self, data: PipelineData) -> None:
        rgb_image = data.require_rgb().astype(np.int32)

        ccm_rgb_image = np.right_shift(rgb_image @ self.matrix + self.bias, 10)
        ccm_rgb_image = np.clip(ccm_rgb_image, 0, self.ctx.saturation.hdr)

        data.rgb_image = ccm_rgb_image.astype(np.uint16)
