import math
import numpy as np
from scipy import ndimage
from scipy.signal import savgol_filter
from datetime import datetime


def extract_median(img_array, target_color, tolerance, y_min, y_max,
                   apply_smooth=False):
    """
    Extract the median path of a colored region in a chart image.

    Parameters
    ----------
    img_array : np.ndarray
        RGB image as (H, W, 3) uint8 array.
    target_color : tuple[int, int, int]
        RGB color to match.
    tolerance : int
        Per-channel tolerance for color matching.
    y_min, y_max : int
        Upper/lower pixel row bounds (inclusive).
    apply_smooth : bool
        If True, apply additional moving-average smoothing after the
        baseline Savitzky-Golay filter to reduce spikes/volatility.

    Returns
    -------
    unique_x : np.ndarray
    smoothed_y : np.ndarray
    """
    target = np.array(target_color, dtype=np.int16)
    lower = np.clip(target - tolerance, 0, 255).astype(np.uint8)
    upper = np.clip(target + tolerance, 0, 255).astype(np.uint8)

    region = img_array[y_min:y_max + 1, :, :]
    mask = np.all((region >= lower) & (region <= upper), axis=-1)

    mask_filled = ndimage.binary_fill_holes(mask)
    structure = np.ones((5, 5))
    mask_cleaned = ndimage.binary_closing(mask_filled, structure=structure)

    y_coords, x_coords = np.where(mask_cleaned)
    if len(x_coords) == 0:
        return np.array([]), np.array([])

    y_coords = y_coords + y_min

    unique_x = np.unique(x_coords)
    median_y = np.array([np.median(y_coords[x_coords == x]) for x in unique_x])

    if len(unique_x) >= 11:
        window = min(11, len(unique_x))
        if window % 2 == 0:
            window -= 1
        if window >= 3:
            smoothed_y = savgol_filter(median_y, window_length=window, polyorder=2)
        else:
            smoothed_y = median_y
    else:
        smoothed_y = median_y

    if apply_smooth and len(smoothed_y) >= 5:
        k = max(5, len(smoothed_y) // 15)
        if k % 2 == 0:
            k += 1
        kernel = np.ones(k) / k
        padded = np.pad(smoothed_y, k // 2, mode="edge")
        smoothed_y = np.convolve(padded, kernel, mode="valid")[:len(unique_x)]

    return unique_x, smoothed_y


def build_calibration(y_calib, x_calib, y_scale="linear"):
    """
    Build mapping functions from two calibration point pairs.

    Parameters
    ----------
    y_calib : ((px1, val1), (px2, val2))
    x_calib : ((px1, date_str1), (px2, date_str2))
    y_scale : str
        'linear' or 'log'.  Log maps pixel space through log10.

    Returns
    -------
    y_func : callable   pixel_y -> real value
    x_func : callable   pixel_x -> datetime
    """
    (py1, v1), (py2, v2) = y_calib

    if y_scale == "log":
        if v1 <= 0 or v2 <= 0:
            raise ValueError("Log Y-axis requires positive reference values.")
        lv1, lv2 = math.log10(v1), math.log10(v2)
        slope = (lv2 - lv1) / (py2 - py1) if py2 != py1 else 0

        def y_func(py):
            return 10 ** (lv1 + slope * (py - py1))
    else:
        slope = (v2 - v1) / (py2 - py1) if py2 != py1 else 0

        def y_func(py):
            return v1 + slope * (py - py1)

    (px1, d1_str), (px2, d2_str) = x_calib
    d1 = _parse_date(d1_str)
    d2 = _parse_date(d2_str)
    d1_ord, d2_ord = d1.toordinal(), d2.toordinal()
    x_slope = (d2_ord - d1_ord) / (px2 - px1) if px2 != px1 else 0

    def x_func(px):
        ordinal = d1_ord + x_slope * (px - px1)
        return datetime.fromordinal(int(round(ordinal)))

    return y_func, x_func


def pixel_to_series(unique_x, median_y, y_func, x_func):
    """Convert pixel-space median path to (date, value) series."""
    dates = [x_func(px) for px in unique_x]
    values = [round(y_func(py), 4) for py in median_y]
    return dates, values


def _parse_date(s):
    """Parse 'YYYY-MM-DD' or 'YYYY-MM' to datetime."""
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{s}'. Use YYYY-MM or YYYY-MM-DD.")
