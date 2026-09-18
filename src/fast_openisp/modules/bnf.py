"""Bilateral noise filter on the luma channel."""

import numpy as np

from fast_openisp.config import BNFParams

from .base import Context, ISPModule, PipelineData
from .helpers import bilateral_filter, gen_gaussian_kernel


class BNF(ISPModule[BNFParams]):
    name = "bnf"

    def __init__(self, params: BNFParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.intensity_weights_lut = self.get_intensity_weights_lut(params.intensity_sigma)
        spatial_weights = gen_gaussian_kernel(kernel_size=5, sigma=params.spatial_sigma)
        # x1024
        self.spatial_weights = (1024 * spatial_weights / spatial_weights.max()).astype(np.int32)

    def execute(self, data: PipelineData) -> None:
        y_image = data.require_y().astype(np.int32)

        bf_y_image = bilateral_filter(
            y_image, self.spatial_weights, self.intensity_weights_lut, right_shift=10
        )
        data.y_image = bf_y_image.astype(np.uint8)

    @staticmethod
    def get_intensity_weights_lut(intensity_sigma: float) -> np.ndarray:
        intensity_diff = np.arange(255**2)
        exp_lut = 1024 * np.exp(-intensity_diff / (2.0 * (255 * intensity_sigma) ** 2))
        return exp_lut.astype(np.int32)  # x1024
