"""Array helpers shared by the ISP modules."""

from collections.abc import Sequence

import numpy as np

from fast_openisp.config import BayerPattern

# (x_start, y_start) of the R, Gr, Gb and B channels for each Bayer pattern
_BAYER_INDICES: dict[str, tuple[tuple[int, int], ...]] = {
    "gbrg": ((0, 1), (1, 1), (0, 0), (1, 0)),
    "rggb": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "bggr": ((1, 1), (0, 1), (1, 0), (0, 0)),
    "grbg": ((1, 0), (0, 0), (1, 1), (0, 1)),
}

Pads = int | Sequence[int]


def get_bayer_indices(pattern: BayerPattern | str) -> tuple[tuple[int, int], ...]:
    """Get (x_start_idx, y_start_idx) for the R, Gr, Gb and B channels of a Bayer array."""
    return _BAYER_INDICES[pattern.lower()]


def split_bayer(bayer_array: np.ndarray, bayer_pattern: BayerPattern | str) -> list[np.ndarray]:
    """Split a Bayer array (H, W) into R, Gr, Gb and B sub-arrays, each (H/2, W/2)."""
    return [bayer_array[y0::2, x0::2] for x0, y0 in get_bayer_indices(bayer_pattern)]


def reconstruct_bayer(
    sub_arrays: Sequence[np.ndarray], bayer_pattern: BayerPattern | str
) -> np.ndarray:
    """Inverse of :func:`split_bayer`."""
    height, width = sub_arrays[0].shape[:2]
    bayer_array = np.empty(shape=(2 * height, 2 * width), dtype=sub_arrays[0].dtype)

    for (x0, y0), sub_array in zip(get_bayer_indices(bayer_pattern), sub_arrays, strict=True):
        bayer_array[y0::2, x0::2] = sub_array

    return bayer_array


def _pad_widths(pads: Pads, ndim: int) -> list[tuple[int, int]]:
    if isinstance(pads, int):
        return [(pads, pads)] * 2 + [(0, 0)] * (ndim - 2)
    if len(pads) == 2:
        return [(pads[0], pads[0]), (pads[1], pads[1])] + [(0, 0)] * (ndim - 2)
    if len(pads) == 4:
        return [(pads[0], pads[1]), (pads[2], pads[3])] + [(0, 0)] * (ndim - 2)
    raise ValueError("pads must be an int or a 2- or 4-element sequence")


def pad(array: np.ndarray, pads: Pads) -> np.ndarray:
    """Reflect-pad the first two axes.

    ``pads`` is an int (all sides), ``(y, x)`` or ``(top, bottom, left, right)``.
    """
    if isinstance(pads, int):
        # Same behaviour as np.pad with a scalar: pads every axis
        return np.pad(array, pads, mode="reflect")
    return np.pad(array, _pad_widths(pads, array.ndim), mode="reflect")


def crop(array: np.ndarray, crops: Pads) -> np.ndarray:
    """Crop the first two axes; ``crops`` has the same format as ``pads`` in :func:`pad`."""
    if isinstance(crops, int):
        top = bottom = left = right = crops
    elif len(crops) == 2:
        top = bottom = crops[0]
        left = right = crops[1]
    elif len(crops) == 4:
        top, bottom, left, right = crops
    else:
        raise ValueError("crops must be an int or a 2- or 4-element sequence")

    height, width = array.shape[:2]
    return array[top : height - bottom, left : width - right, ...]


def shift_array(padded_array: np.ndarray, window_size: int | tuple[int, int]) -> list[np.ndarray]:
    """Return the ``wy * wx`` shifted views of a padded array within a window.

    The unshifted (original) array is in the middle of the list.
    """
    wy, wx = window_size if isinstance(window_size, tuple) else (window_size, window_size)
    assert wy % 2 == 1 and wx % 2 == 1, "only odd window size is valid"

    height = padded_array.shape[0] - wy + 1
    width = padded_array.shape[1] - wx + 1

    return [
        padded_array[y0 : y0 + height, x0 : x0 + width, ...] for y0 in range(wy) for x0 in range(wx)
    ]


def gen_gaussian_kernel(kernel_size: int | tuple[int, int], sigma: float) -> np.ndarray:
    wy, wx = kernel_size if isinstance(kernel_size, tuple) else (kernel_size, kernel_size)

    x = np.arange(wx) - wx // 2
    if wx % 2 == 0:
        x = x + 0.5

    y = np.arange(wy) - wy // 2
    if wy % 2 == 0:
        y = y + 0.5

    y, x = np.meshgrid(y, x)

    kernel = np.exp(-(x**2 + y**2) / (2 * sigma**2))
    return kernel / kernel.sum()


def generic_filter(array: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Filter an integer array with the given kernel (normalised by the kernel sum)."""
    kh, kw = kernel.shape[:2]
    flat_kernel = kernel.flatten()

    padded_array = pad(array, pads=(kh // 2, kw // 2))
    shifted_arrays = shift_array(padded_array, window_size=(kh, kw))

    filtered_array = np.zeros_like(array)
    weights = np.zeros_like(array)

    for i, shifted_array in enumerate(shifted_arrays):
        filtered_array += flat_kernel[i] * shifted_array
        weights += flat_kernel[i]

    return (filtered_array / weights).astype(array.dtype)


def mean_filter(array: np.ndarray, filter_size: int = 3) -> np.ndarray:
    """Box filter with an odd ``filter_size``."""
    assert filter_size % 2 == 1, "only odd filter size is valid"

    padded_array = pad(array, pads=filter_size // 2)
    shifted_arrays = shift_array(padded_array, window_size=filter_size)
    total = np.zeros(shifted_arrays[0].shape, dtype=np.result_type(array.dtype, np.int64))
    for shifted in shifted_arrays:
        total += shifted
    return (total / filter_size**2).astype(array.dtype)


def bilateral_filter(
    array: np.ndarray,
    spatial_weights: np.ndarray,
    intensity_weights_lut: np.ndarray,
    right_shift: int = 0,
) -> np.ndarray:
    """Bilateral filter for integer arrays.

    :param spatial_weights: (h, w) spatial Gaussian kernel
    :param intensity_weights_lut: LUT mapping squared intensity distance to a weight
    :param right_shift: right shift applied to the combined weight to avoid overflow
    """
    filter_height, filter_width = spatial_weights.shape[:2]
    flat_spatial = spatial_weights.flatten()

    padded_array = pad(array, pads=(filter_height // 2, filter_width // 2))
    shifted_arrays = shift_array(padded_array, window_size=(filter_height, filter_width))

    bf_array = np.zeros_like(array)
    weights = np.zeros_like(array)

    for i, shifted_array in enumerate(shifted_arrays):
        intensity_diff = (shifted_array - array) ** 2
        weight = intensity_weights_lut[intensity_diff] * flat_spatial[i]
        weight = np.right_shift(weight, right_shift)  # to avoid overflow

        bf_array += weight * shifted_array
        weights += weight

    return (bf_array / weights).astype(array.dtype)
