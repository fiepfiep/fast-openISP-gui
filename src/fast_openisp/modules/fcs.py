"""False color suppression: desaturates chroma near strong edges."""

import numpy as np

from fast_openisp.config import FCSParams

from .base import Context, ISPModule, PipelineData


class FCS(ISPModule[FCSParams]):
    name = "fcs"

    def __init__(self, params: FCSParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        threshold_delta = np.clip(params.delta_max - params.delta_min, 1e-6, None)
        self.slope = -np.array(65536 / threshold_delta, dtype=np.int32)  # x65536

    def execute(self, data: PipelineData) -> None:
        cbcr_image = data.require_cbcr().astype(np.int32)
        edge_map = data.require_edge_map()

        gain_map = self.slope * (np.abs(edge_map) - self.params.delta_max)
        gain_map = np.clip(gain_map, 0, 65536)
        fcs_cbcr_image = np.right_shift(gain_map[..., None] * (cbcr_image - 128), 16) + 128
        fcs_cbcr_image = np.clip(fcs_cbcr_image, 0, self.ctx.saturation.sdr)

        data.cbcr_image = fcs_cbcr_image.astype(np.uint8)
