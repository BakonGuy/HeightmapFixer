8-BIT HEIGHTMAP FIXER
=====================

Use
---
Select any number of heightmap images in Explorer and drag them together onto
"Fix Heightmaps.cmd".

Each result is saved beside its source as:
    original-name_16bit_fixed.png

The source files are never overwritten. The first run may install the small
Python dependencies Pillow and NumPy if they are not already available.

What it does
------------
The tool does more than change the PNG bit-depth. It treats each 8-bit value as
a range of possible true heights, then reconstructs smooth sub-level values from
the surrounding terrain slope.

It also detects images enlarged with nearest-neighbor scaling (for example, a
256x256 height field stored as repeated 4x4 blocks in a 1024x1024 image). It
collapses those blocks to the true source grid, reconstructs there, then returns
to the original dimensions using floating-point bicubic surface interpolation
and a light reconstruction filter. This is important because changing bit depth
alone cannot remove spatially replicated staircase geometry.

The output is a true single-channel unsigned 16-bit grayscale PNG. RGB images
are converted to luminance, and alpha is discarded because heightmaps contain
one scalar height per pixel.

Command line (optional)
-----------------------
    python fix_heightmaps.py map1.png map2.png

For unusually broad terraces, try more iterations:
    python fix_heightmaps.py --iterations 800 map.png

The default is 400; accepted values are 1 through 5000.
