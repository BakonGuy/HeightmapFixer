#!/usr/bin/env python3
"""Reconstruct smooth 16-bit heightmaps from quantized 8-bit images."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def replication_factor(values: np.ndarray, maximum: int = 16) -> int:
    """Return the largest exact N x N nearest-neighbor replication factor."""
    height, width = values.shape
    for factor in range(min(maximum, height, width), 1, -1):
        if height % factor or width % factor:
            continue
        blocks = values.reshape(height // factor, factor, width // factor, factor)
        reference = blocks[:, :1, :, :1]
        if np.all(blocks == reference):
            return factor
    return 1


def gaussian_blur(values: np.ndarray, sigma: float) -> np.ndarray:
    """Small separable floating-point blur used only after surface resampling."""
    if sigma <= 0:
        return values
    radius = max(1, int(np.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()

    def convolve_axis(data: np.ndarray, axis: int) -> np.ndarray:
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius, radius)
        padded = np.pad(data, pad, mode="reflect")
        return np.apply_along_axis(lambda line: np.convolve(line, kernel, mode="valid"),
                                   axis, padded)

    return convolve_axis(convolve_axis(values, 1), 0)


def dequantize(values: np.ndarray, iterations: int, tolerance: float) -> np.ndarray:
    """Find the smoothest surface consistent with every input quantization bin.

    Each 8-bit sample represents an interval rather than an exact height.  Projected
    diffusion lets neighboring slopes choose a sub-level value inside that interval.
    Consequently the pass removes terraces without blurring across more than half an
    original 8-bit level or moving actual terrain features to a different level.
    """
    center = values.astype(np.float32) * 257.0
    half_bin = 128.5
    low = np.maximum(0.0, center - half_bin)
    high = np.minimum(65535.0, center + half_bin)
    height = center.copy()

    for step in range(iterations):
        padded = np.pad(height, 1, mode="edge")
        # Eight-neighbor diffusion is less axis-biased than a four-neighbor stencil.
        axial = (
            padded[:-2, 1:-1] + padded[2:, 1:-1]
            + padded[1:-1, :-2] + padded[1:-1, 2:]
        )
        diagonal = (
            padded[:-2, :-2] + padded[:-2, 2:]
            + padded[2:, :-2] + padded[2:, 2:]
        )
        candidate = (axial * 2.0 + diagonal) / 12.0
        candidate = np.clip(candidate, low, high)

        change = float(np.max(np.abs(candidate - height)))
        height = candidate
        if change < tolerance:
            break

    return height


def convert(source: Path, output_dir: Path | None, iterations: int) -> Path:
    with Image.open(source) as image:
        if image.width < 2 or image.height < 2:
            raise ValueError("image must be at least 2 x 2 pixels")

        # Heightmaps are scalar data. RGB inputs are converted using standard
        # luminance; fully opaque alpha is harmless and deliberately discarded.
        if image.mode in {"I;16", "I;16L", "I;16B"}:
            raise ValueError("input is already 16-bit")
        gray = image.convert("L")
        pixels = np.asarray(gray, dtype=np.uint8)

    original_size = (pixels.shape[1], pixels.shape[0])
    factor = replication_factor(pixels)
    if factor > 1:
        print(f"  Detected exact {factor}x{factor} pixel replication; "
              f"reconstructing the true {original_size[0] // factor}x"
              f"{original_size[1] // factor} source grid.")
        pixels = pixels[::factor, ::factor]

    surface = dequantize(pixels, iterations=iterations, tolerance=0.02)

    if factor > 1:
        # Resize an F-mode image so interpolation happens in floating-point height
        # space. Resizing an L/I;16 image here would quantize or truncate the result.
        float_image = Image.fromarray(surface.astype(np.float32), mode="F")
        surface = np.asarray(
            float_image.resize(original_size, resample=Image.Resampling.BICUBIC),
            dtype=np.float32,
        )
        # A light reconstruction filter suppresses bicubic ringing and remaining
        # shelf edges while retaining the terrain wavelengths present in the source.
        surface = gaussian_blur(surface, sigma=max(0.65, factor * 0.32))

    fixed = np.rint(np.clip(surface, 0.0, 65535.0)).astype(np.uint16)
    destination_dir = output_dir if output_dir else source.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source.stem}_16bit_fixed.png"

    # Pillow's I;16 mode writes a true single-channel, unsigned 16-bit PNG.
    Image.fromarray(fixed).save(destination, compress_level=6)
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert one or more 8-bit heightmaps to de-terraced 16-bit PNGs."
    )
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--iterations", type=int, default=400,
                        help="smoothing iterations (default: 400)")
    parser.add_argument("--output-dir", type=Path,
                        help="put every result in this directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.iterations <= 5000:
        print("Error: --iterations must be between 1 and 5000", file=sys.stderr)
        return 2

    failures = 0
    for source in args.images:
        try:
            if not source.is_file():
                raise FileNotFoundError("file not found")
            print(f"Processing: {source}")
            result = convert(source, args.output_dir, args.iterations)
            print(f"Created:    {result}")
        except Exception as exc:
            failures += 1
            print(f"FAILED: {source} ({exc})", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
