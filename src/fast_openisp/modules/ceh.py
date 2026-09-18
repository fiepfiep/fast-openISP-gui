"""Contrast enhancement: contrast-limited adaptive histogram equalisation (CLAHE) on luma."""

import math

import numpy as np

from fast_openisp.config import CEHParams

from .base import Context, ISPModule, PipelineData
from .helpers import crop, pad


class CEH(ISPModule[CEHParams]):
    name = "ceh"

    def __init__(self, params: CEHParams, ctx: Context) -> None:
        super().__init__(params, ctx)
        self.y_tiles, self.x_tiles = params.tiles

    def _setup(self, height: int, width: int) -> None:
        self.tile_height = math.ceil(height / self.y_tiles)
        self.tile_width = math.ceil(width / self.x_tiles)

        y_pads = self.tile_height * self.y_tiles - height
        x_pads = self.tile_width * self.x_tiles - width
        self.pads = (y_pads // 2, y_pads - y_pads // 2, x_pads // 2, x_pads - x_pads // 2)

        # Weights for LUTs interpolation, x1024
        self.left_lut_weights = np.linspace(1024, 0, self.tile_width, dtype=np.int32).reshape(
            (1, -1)
        )
        self.top_lut_weights = np.linspace(1024, 0, self.tile_height, dtype=np.int32).reshape(
            (-1, 1)
        )

        # LUTs w.r.t. tiles
        self.luts = np.empty(shape=(self.y_tiles, self.x_tiles, 256), dtype=np.uint8)

    def execute(self, data: PipelineData) -> None:
        y_image = data.require_y().astype(np.int32)
        self._setup(*y_image.shape[:2])
        y_image = pad(y_image, pads=self.pads)
        th, tw = self.tile_height, self.tile_width

        # ---------- Generate tile-wise look-up tables ----------
        for ty in range(self.y_tiles):
            for tx in range(self.x_tiles):
                y_tile = y_image[ty * th : (ty + 1) * th, tx * tw : (tx + 1) * tw]
                self.luts[ty, tx] = self._get_tile_lut(y_tile)

        # ---------- Interpolate and apply LUTs for different image blocks ----------
        ceh_y_image = np.empty_like(y_image).astype(np.uint8)
        for iy in range(self.y_tiles + 1):
            for ix in range(self.x_tiles + 1):
                y0 = iy * th - th // 2
                y1 = min(y0 + th, y_image.shape[0])
                x0 = ix * tw - tw // 2
                x1 = min(x0 + tw, y_image.shape[1])
                y0 = max(y0, 0)
                x0 = max(x0, 0)

                y_block = y_image[y0:y1, x0:x1]

                if self._is_corner_block(ix, iy):
                    lut_y_idx = 0 if iy == 0 else self.y_tiles - 1
                    lut_x_idx = 0 if ix == 0 else self.x_tiles - 1
                    lut = self.luts[lut_y_idx, lut_x_idx]
                    ceh_y_image[y0:y1, x0:x1] = lut[y_block]

                elif self._is_top_or_bottom_block(ix, iy):
                    lut_y_idx = 0 if iy == 0 else self.y_tiles - 1
                    left_lut = self.luts[lut_y_idx, ix - 1]
                    right_lut = self.luts[lut_y_idx, ix]
                    ceh_y_image[y0:y1, x0:x1] = self._interp_top_bottom_block(
                        y_block, left_lut, right_lut
                    )

                elif self._is_left_or_right_block(ix, iy):
                    lut_x_idx = 0 if ix == 0 else self.x_tiles - 1
                    top_lut = self.luts[iy - 1, lut_x_idx]
                    bottom_lut = self.luts[iy, lut_x_idx]
                    ceh_y_image[y0:y1, x0:x1] = self._interp_left_right_block(
                        y_block, top_lut, bottom_lut
                    )

                else:
                    tl_lut = self.luts[iy - 1, ix - 1]
                    tr_lut = self.luts[iy - 1, ix]
                    bl_lut = self.luts[iy, ix - 1]
                    br_lut = self.luts[iy, ix]
                    ceh_y_image[y0:y1, x0:x1] = self._interp_neighbor_block(
                        y_block, tl_lut, tr_lut, bl_lut, br_lut
                    )

        data.y_image = crop(ceh_y_image, self.pads)

    def _get_tile_lut(self, tiled_array: np.ndarray) -> np.ndarray:
        sdr = self.ctx.saturation.sdr
        hist = np.histogram(tiled_array, bins=256, range=(0, sdr))[0]
        clipped_hist = np.clip(hist, 0, self.params.clip_limit * max(hist))

        num_clipped_pixels = (hist - clipped_hist).sum()

        hist = clipped_hist + num_clipped_pixels / 256
        pdf = hist / hist.sum()
        cdf = np.cumsum(pdf)

        return (cdf * sdr).astype(np.uint8)

    def _interp_top_bottom_block(
        self, block: np.ndarray, left_lut: np.ndarray, right_lut: np.ndarray
    ) -> np.ndarray:
        return np.right_shift(
            self.left_lut_weights * left_lut[block].astype(np.int32)
            + (1024 - self.left_lut_weights) * right_lut[block].astype(np.int32),
            10,
        ).astype(np.uint8)

    def _interp_left_right_block(
        self, block: np.ndarray, top_lut: np.ndarray, bottom_lut: np.ndarray
    ) -> np.ndarray:
        return np.right_shift(
            self.top_lut_weights * top_lut[block].astype(np.int32)
            + (1024 - self.top_lut_weights) * bottom_lut[block].astype(np.int32),
            10,
        ).astype(np.uint8)

    def _interp_neighbor_block(
        self,
        block: np.ndarray,
        tl_lut: np.ndarray,
        tr_lut: np.ndarray,
        bl_lut: np.ndarray,
        br_lut: np.ndarray,
    ) -> np.ndarray:
        top_block = self._interp_top_bottom_block(block, tl_lut, tr_lut).astype(np.int32)
        bottom_block = self._interp_top_bottom_block(block, bl_lut, br_lut).astype(np.int32)
        return np.right_shift(
            self.top_lut_weights * top_block + (1024 - self.top_lut_weights) * bottom_block, 10
        ).astype(np.uint8)

    def _is_corner_block(self, ix: int, iy: int) -> bool:
        """Determine if the current image block is located in a corner region."""
        return iy in (0, self.y_tiles) and ix in (0, self.x_tiles)

    def _is_top_or_bottom_block(self, ix: int, iy: int) -> bool:
        return iy in (0, self.y_tiles) and not self._is_corner_block(ix, iy)

    def _is_left_or_right_block(self, ix: int, iy: int) -> bool:
        return ix in (0, self.x_tiles) and not self._is_corner_block(ix, iy)
