"""Chroma noise filter on the Bayer data. Uses the white-balance gains applied by AWB."""

import numpy as np

from fast_openisp.config import CNFParams

from .base import ISPModule, PipelineData, to_fixed
from .helpers import mean_filter, reconstruct_bayer, split_bayer


class CNF(ISPModule[CNFParams]):
    name = "cnf"

    def cnd(
        self, bayer: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        threshold = self.params.diff_threshold
        r, gr, gb, b = split_bayer(bayer, self.ctx.bayer_pattern)
        avg_r = mean_filter(r, filter_size=5)
        avg_g = np.right_shift(mean_filter(gr, filter_size=5) + mean_filter(gb, filter_size=5), 1)
        avg_b = mean_filter(b, filter_size=5)

        is_r_noise = (
            (r - avg_g > threshold)
            * (r - avg_b > threshold)
            * (avg_r - avg_g > threshold)
            * (avg_r - avg_b < threshold)
        )
        is_b_noise = (
            (b - avg_g > threshold)
            * (b - avg_r > threshold)
            * (avg_b - avg_g > threshold)
            * (avg_b - avg_r < threshold)
        )

        return avg_r, avg_g, avg_b, is_r_noise, is_b_noise

    @staticmethod
    def cnc(
        array: np.ndarray,
        avg_g: np.ndarray,
        avg_c1: np.ndarray,
        avg_c2: np.ndarray,
        y: np.ndarray,
        gain: int,
    ) -> np.ndarray:
        assert array.dtype == np.int32

        if gain <= 1024:  # x1024
            damp_factor = 256  # x256
        elif 1024 < gain <= 1229:
            damp_factor = 128
        else:
            damp_factor = 77

        max_avg = np.maximum(avg_g, avg_c2)
        signal_gap = array - max_avg
        chroma_corrected = max_avg + np.right_shift(damp_factor * signal_gap, 8)

        fade1 = (
            (y <= 30) * 1.0
            + (y > 30) * (y <= 50) * 0.9
            + (y > 50) * (y <= 70) * 0.8
            + (y > 70) * (y <= 100) * 0.7
            + (y > 100) * (y <= 150) * 0.6
            + (y > 150) * (y <= 200) * 0.3
            + (y > 200) * (y <= 250) * 0.1
        )
        fade2 = (
            (avg_c1 <= 30) * 1.0
            + (avg_c1 > 30) * (avg_c1 <= 50) * 0.9
            + (avg_c1 > 50) * (avg_c1 <= 70) * 0.8
            + (avg_c1 > 70) * (avg_c1 <= 100) * 0.6
            + (avg_c1 > 100) * (avg_c1 <= 150) * 0.5
            + (avg_c1 > 150) * (avg_c1 <= 200) * 0.3
        )
        fade = fade1 * fade2

        cnc = fade * chroma_corrected + (1 - fade) * array
        return cnc.astype(np.int32)

    def execute(self, data: PipelineData) -> None:
        bayer = data.bayer.astype(np.int32)
        r_gain = to_fixed(data.awb_gains[0], 1024)
        b_gain = to_fixed(data.awb_gains[3], 1024)

        r, gr, gb, b = split_bayer(bayer, self.ctx.bayer_pattern)
        avg_r, avg_g, avg_b, is_r_noise, is_b_noise = self.cnd(bayer)

        # y = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
        y = np.right_shift(306 * avg_r + 601 * avg_g + 117 * avg_b, 10)
        r_cnc = self.cnc(r, avg_g, avg_r, avg_b, y, r_gain)
        b_cnc = self.cnc(b, avg_g, avg_b, avg_r, y, b_gain)
        r_cnc = is_r_noise * r_cnc + ~is_r_noise * r
        b_cnc = is_b_noise * b_cnc + ~is_b_noise * b

        cnf_bayer = reconstruct_bayer([r_cnc, gr, gb, b_cnc], self.ctx.bayer_pattern)
        cnf_bayer = np.clip(cnf_bayer, 0, self.ctx.saturation.hdr)

        data.bayer = cnf_bayer.astype(np.uint16)
