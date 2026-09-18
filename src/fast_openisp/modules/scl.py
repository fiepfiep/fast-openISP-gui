"""Scaler: resizes the RGB or YCbCr result."""

import cv2
import numpy as np

from fast_openisp.config import SCLParams

from .base import ISPModule, PipelineData, PipelineError


class SCL(ISPModule[SCLParams]):
    name = "scl"

    def _resize(self, image: np.ndarray) -> np.ndarray:
        # In preview mode the input is downscaled, so the target size is scaled as well.
        factor = self.ctx.preview_factor
        size = (max(1, self.params.width // factor), max(1, self.params.height // factor))
        return np.asarray(cv2.resize(image, dsize=size, interpolation=cv2.INTER_LINEAR))

    def execute(self, data: PipelineData) -> None:
        if data.y_image is not None and data.cbcr_image is not None:
            data.y_image = self._resize(data.y_image)
            data.cbcr_image = self._resize(data.cbcr_image)
        elif data.rgb_image is not None:
            data.rgb_image = self._resize(data.rgb_image)
        else:
            raise PipelineError("SCL cannot resize a Bayer array (enable CFA)")
