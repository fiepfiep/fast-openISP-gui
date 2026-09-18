"""Non-local means denoising on luma."""

import numpy as np

from fast_openisp.config import NLMParams

from .base import Context, ISPModule, PipelineData
from .helpers import mean_filter, pad, shift_array


class NLM(ISPModule[NLMParams]):
    name = "nlm"

    def __init__(self, params: NLMParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.distance_weights_lut = self.get_distance_weights_lut(h=params.h)

    def execute(self, data: PipelineData) -> None:
        y_image = data.require_y().astype(np.int32)
        window = self.params.search_window_size

        padded_y_image = pad(y_image, pads=window // 2)
        shifted_arrays = shift_array(padded_y_image, window_size=window)

        nlm_y_image = np.zeros_like(y_image)
        weights = np.zeros_like(y_image)

        for shifted_y_image in shifted_arrays:
            distance = mean_filter(
                (y_image - shifted_y_image) ** 2, filter_size=self.params.patch_size
            )
            weight = self.distance_weights_lut[distance]
            nlm_y_image += shifted_y_image * weight
            weights += weight

        data.y_image = (nlm_y_image / weights).astype(np.uint8)

    @staticmethod
    def get_distance_weights_lut(h: float) -> np.ndarray:
        distance = np.arange(255**2)
        lut = 1024 * np.exp(-distance / h**2)
        return lut.astype(np.int32)  # x1024
