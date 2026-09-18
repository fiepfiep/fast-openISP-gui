"""Color space conversion RGB → YCbCr (BT.601, limited range)."""

import numpy as np

from fast_openisp.config import CSCParams

from .base import Context, ISPModule, PipelineData


class CSC(ISPModule[CSCParams]):
    name = "csc"

    def __init__(self, params: CSCParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.matrix = np.array(
            [[66, 129, 25], [-38, -74, 112], [112, -94, -18]], dtype=np.int32
        ).T  # x256
        self.bias = np.array([16, 128, 128], dtype=np.int32).reshape(1, 1, 3)

    def execute(self, data: PipelineData) -> None:
        rgb_image = data.require_rgb().astype(np.int32)

        ycrcb_image = (np.right_shift(rgb_image @ self.matrix, 8) + self.bias).astype(np.uint8)

        data.y_image = ycrcb_image[..., 0]
        data.cbcr_image = ycrcb_image[..., 1:]
