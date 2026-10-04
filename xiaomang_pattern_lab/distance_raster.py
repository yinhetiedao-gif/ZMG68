"""Exact separable Euclidean distance transform in world units (NumPy only).

Foreground boundary pixels are zero; outside is always zero, even inverted.
The one-dimensional lower envelope keeps preprocessing linear in pixel count.
"""
from collections import OrderedDict
from threading import RLock
import math
import numpy as np

_CACHE = OrderedDict()
_LOCK = RLock()
_MAX_BYTES = 64 * 1024 * 1024


def _edt_line(values, spacing):
    finite = np.flatnonzero(np.isfinite(values))
    result = np.full(len(values), np.inf)
    if not len(finite):
        return result
    sites, breaks = [int(finite[0])], [-math.inf, math.inf]
    squared = spacing * spacing
    for raw in finite[1:]:
        q = int(raw)
        while True:
            p = sites[-1]
            cross = ((values[q] - values[p]) / squared + q*q - p*p) / (2*(q-p))
            if cross > breaks[-2]:
                break
            sites.pop(); breaks.pop()
        breaks[-1] = cross
        sites.append(q); breaks.append(math.inf)
    k = 0
    for q in range(len(values)):
        while breaks[k+1] < q:
            k += 1
        result[q] = squared * (q-sites[k])**2 + values[sites[k]]
    return result


def _foreground_mask(image, threshold):
    width, height, pixels = image
    return 1 - np.asarray(pixels, dtype=np.float64).reshape(height, width)/255 >= threshold


def _boundary_distance(mask, bounds):
    height, width = mask.shape
    padded = np.pad(mask, 1, constant_values=False)
    interior = (mask & padded[:-2, 1:-1] & padded[2:, 1:-1]
                & padded[1:-1, :-2] & padded[1:-1, 2:])
    boundary = mask & ~interior
    distances = np.where(boundary, 0., np.inf)
    dx = (bounds[2]-bounds[0])/max(width-1, 1)
    dy = (bounds[3]-bounds[1])/max(height-1, 1)
    if boundary.any():
        for row in range(height):
            distances[row] = _edt_line(distances[row], dx)
        for column in range(width):
            distances[:, column] = _edt_line(distances[:, column], dy)
        distances = np.sqrt(distances)
    else:
        distances.fill(0)
    distances[~mask] = 0
    return distances


def distance_raster(image, bounds, threshold, maximum, invert):
    width, height, pixels = image
    # Pixel data are pinned by ImageField, so changed assets cannot hit an old key.
    key = (image, tuple(bounds), threshold, maximum, invert)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        mask = _foreground_mask(image, threshold)
        distances = _boundary_distance(mask, bounds)
        divisor = maximum if maximum > 0 else float(distances.max())
        values = np.minimum(distances/max(divisor, 1e-12), 1)
        # Inversion is applied after interpolation by the scalar sampler so
        # foreground edge samples are exact complements; outside stays zero.
        values.setflags(write=False)
        mask.setflags(write=False)
        result = (width, height, values.ravel(), mask.ravel())
        size = values.nbytes + mask.nbytes + width*height*8
        if size <= _MAX_BYTES:
            while _CACHE and (sum(v[2].nbytes*2+v[3].nbytes for v in _CACHE.values()) + size > _MAX_BYTES or len(_CACHE) >= 8):
                _CACHE.popitem(last=False)
            _CACHE[key] = result
        return result
