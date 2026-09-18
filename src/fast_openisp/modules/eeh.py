"""Edge enhancement (unsharp masking with a piecewise-linear gain curve) on luma."""

import numpy as np

from fast_openisp.config import EEHParams

from .base import Context, ISPModule, PipelineData, to_fixed
from .helpers import gen_gaussian_kernel, generic_filter


class EEH(ISPModule[EEHParams]):
    name = "eeh"

    def __init__(self, params: EEHParams, ctx: Context) -> None:
        super().__init__(params, ctx)

        kernel = gen_gaussian_kernel(kernel_size=5, sigma=1.2)
        self.gaussian = (1024 * kernel / kernel.max()).astype(np.int32)  # x1024

        edge_gain = to_fixed(params.edge_gain, 256)  # x256
        t1, t2 = params.flat_threshold, params.edge_threshold
        threshold_delta = np.clip(t2 - t1, 1e-6, None)
        self.middle_slope = np.array(edge_gain * t2 / threshold_delta, dtype=np.int32)  # x256
        self.middle_intercept = -np.array(
            edge_gain * t1 * t2 / threshold_delta, dtype=np.int32
        )  # x256
        self.edge_gain = np.array(edge_gain, dtype=np.int32)  # x256

    def execute(self, data: PipelineData) -> None:
        y_image = data.require_y().astype(np.int32)
        p = self.params

        delta = y_image - generic_filter(y_image, self.gaussian)
        sign_map = np.sign(delta)
        abs_delta = np.abs(delta)

        middle_delta = np.right_shift(self.middle_slope * abs_delta + self.middle_intercept, 8)
        edge_delta = np.right_shift(self.edge_gain * abs_delta, 8)
        enhanced_delta = (abs_delta > p.flat_threshold) * (
            abs_delta <= p.edge_threshold
        ) * middle_delta + (abs_delta > p.edge_threshold) * edge_delta

        enhanced_delta = sign_map * np.clip(enhanced_delta, 0, p.delta_threshold)
        eeh_y_image = np.clip(y_image + enhanced_delta, 0, self.ctx.saturation.sdr)

        data.y_image = eeh_y_image.astype(np.uint8)
        data.edge_map = delta
