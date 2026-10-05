"""Distance consumer's cached axial statistics; never changes scalar samples."""
from collections import OrderedDict
from threading import RLock
import math
import numpy as np

_CACHE = OrderedDict()
_LOCK = RLock()
# Algorithm constants are cache dependencies, not document or screen state.
_RAW_COHERENCE = .9
_MIN_COHERENCE = .05
_EXPANDED_RADIUS = 1.5
_KERNEL_RADIUS = 3
# An EDT's regular interior slope is approximately constant. Near medial
# ridges central differences cancel partially even when nonzero; prefer the
# neighborhood axis if the sample is substantially weaker than that slope.
_RAW_MAGNITUDE_RATIO = .75
_POLICY = (2, _RAW_COHERENCE, _MIN_COHERENCE, _EXPANDED_RADIUS, _KERNEL_RADIUS,
           _RAW_MAGNITUDE_RATIO)


def axial_mean(cosine, sine):
    return .5 * math.degrees(math.atan2(sine, cosine))


def _blur(array, sigma_x, sigma_y):
    for axis, sigma in ((0, sigma_y), (1, sigma_x)):
        radius = max(1, math.ceil(_KERNEL_RADIUS*sigma))
        offsets = np.arange(-radius, radius+1)
        kernel = np.exp(-.5*(offsets/sigma)**2)
        kernel /= kernel.sum()
        # Same zero-padded Gaussian, in NumPy's compiled convolution instead
        # of one full image allocation per tap. No new dependency/resampling.
        array = np.apply_along_axis(
            lambda line: np.convolve(np.pad(line, (radius, radius)), kernel, mode='valid'),
            axis, array)
    return array


def prepare_orientation(field, bounds):
    field.prepare_distance(bounds)
    key = (field._prepared_pixels, tuple(bounds), field.world_mm_per_unit,
           field.threshold, field.invert, field.auto_normalize, field.max_distance_mm, _POLICY)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        width, height, values, mask = field._distance_pixels
        plane = values.reshape(height, width)
        dx = max((bounds[2]-bounds[0])/max(width-1, 1), 1e-6)
        dy = max((bounds[3]-bounds[1])/max(height-1, 1), 1e-6)
        gx = np.gradient(plane, dx, axis=1) if width > 1 else np.zeros_like(plane)
        gy = np.gradient(plane, dy, axis=0) if height > 1 else np.zeros_like(plane)
        magnitude = np.hypot(gx, gy)*mask.reshape(height, width)
        reliable = magnitude > 1e-9
        weight = np.where(reliable, magnitude, 0)
        divisor = np.maximum(gx*gx+gy*gy, 1e-30)
        cosine = (gx*gx-gy*gy)/divisor*weight
        sine = 2*gx*gy/divisor*weight
        # Scalar peak / interior slope estimates local-feature world scale.
        # No instance spacing/count, viewport, or iteration order is involved.
        slope = float(np.median(magnitude[reliable])) if reliable.any() else 0
        sigma = max(2*max(dx, dy), float(plane.max())/max(2*slope, 1e-9))
        # Keep kernels bounded on low-resolution and pathological inputs.
        sigma = min(sigma, max(bounds[2]-bounds[0], bounds[3]-bounds[1])/8)
        planes = []
        for expansion in (1., _EXPANDED_RADIUS):
            planes.append(tuple(_blur(a, max(sigma*expansion/dx, .5),
                                     max(sigma*expansion/dy, .5)) for a in (cosine, sine, weight)))
        result = (field._distance_pixels, planes, dx, dy, sigma, slope)
        for group in planes:
            for a in group: a.setflags(write=False)
        size = sum(a.nbytes for group in planes for a in group)
        if size <= 64*1024*1024:
            while _CACHE and (len(_CACHE) >= 4 or
                sum(sum(a.nbytes for group in v[1] for a in group) for v in _CACHE.values())+size > 64*1024*1024):
                _CACHE.popitem(last=False)
            _CACHE[key] = result
        return result


def _sample(plane, x, y):
    left, top = int(x), int(y)
    right, bottom = min(left+1, plane.shape[1]-1), min(top+1, plane.shape[0]-1)
    tx, ty = x-left, y-top
    return float((plane[top,left]*(1-tx)+plane[top,right]*tx)*(1-ty)
                 +(plane[bottom,left]*(1-tx)+plane[bottom,right]*tx)*ty)


def stabilized_angle(prepared, bounds, x, y, raw_angle, raw_magnitude):
    owner, groups, _, _, _, slope = prepared
    width, height, _, mask = owner
    u = (x-bounds[0])/max(bounds[2]-bounds[0], 1e-9)
    v = (y-bounds[1])/max(bounds[3]-bounds[1], 1e-9)
    if not 0 <= u <= 1 or not 0 <= v <= 1:
        return None
    px, py = u*(width-1), v*(height-1)
    if not mask[min(int(py+.5),height-1)*width+min(int(px+.5),width-1)]:
        return None
    c, s, w = (_sample(a, px, py) for a in groups[0])
    coherence = math.hypot(c,s)/max(w,1e-30)
    if raw_magnitude > max(1e-9, slope*_RAW_MAGNITUDE_RATIO) and coherence >= _RAW_COHERENCE:
        return (raw_angle+90)%180-90
    if coherence < _MIN_COHERENCE:
        c, s, w = (_sample(a, px, py) for a in groups[1])
        coherence = math.hypot(c,s)/max(w,1e-30)
    if w <= 1e-9 or coherence < _MIN_COHERENCE:
        return None
    return axial_mean(c,s)
