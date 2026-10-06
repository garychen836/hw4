"""Clean up product photos for the website.

Most product photos are cut-out garments flattened onto a pure black background,
which leaves hard, jagged edges. This script:
  1. finds the background (near-black or near-white pixels connected to the border,
     so black logos or white prints *inside* the garment are kept),
  2. softens the cut-out edge (shrink the mask 1px to drop the dark fringe, then blur),
  3. places the garment on the site's light-gray card color with a soft shadow,
  4. pads it to a centered square.

Originals in data/products/ are never changed; cleaned copies go to data/products_clean/.
Neither folder is committed to git. The API serves the cleaned copy when it exists.

Run from the HW 4 folder:
    .venv/bin/python backend/clean_images.py
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "products"
DST = ROOT / "data" / "products_clean"

CANVAS = (244, 244, 244)  # matches --bg-light in frontend/src/index.css
OUT_SIZE = 900
BLACK_MAX = 28  # a pixel is "background black" if every channel is below this
WHITE_MIN = 246  # a pixel is "background white" if every channel is above this
GAP_MIN_SHARE = 0.002  # trapped black pockets bigger than 0.2% of the photo are background
# Photos whose cut-out is too rough to clean well: serve the untouched original instead
# (main.py falls back to data/products/ when no cleaned copy exists).
# Cut-outs with stair-step edges: outline smoothing radius in pixels (stronger than the default edge blur).
SMOOTH_OUTLINE = {"basic-hoodie-big-yale.jpg": 5}
KEEP_ORIGINAL = {
    "boola-boola-t-shirt.jpg",  # white slivers at collar and sleeve in the source cut-out
    "football-left-chest-t-shirt.jpg",  # same navy-tee template as Boola Boola: white slivers
    "track-field-left-chest-t-shirt.jpg",  # same template
}
FRINGE_MAX_WIDTH = 3  # light strips at most ~6 px wide along the cut edge are leftover fringe


def connected_to(candidate: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """Pixels in `candidate` whose connected region touches `seed`."""
    labels, _ = ndimage.label(candidate)
    touching = np.unique(labels[seed & (labels > 0)])
    return np.isin(labels, touching)


def background_mask(rgb: np.ndarray, kind: str) -> Image.Image:
    """255 where the pixel is background connected to the image border."""
    near_black = rgb.max(axis=2) < BLACK_MAX
    near_white = rgb.min(axis=2) > WHITE_MIN
    border = np.zeros(near_black.shape, dtype=bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True

    first, second = (near_black, near_white) if kind == "black" else (near_white, near_black)
    background = connected_to(first, border)
    # Some photos are a white box inside a black frame (or the reverse):
    # also remove the other background color where it touches the first.
    touching = ndimage.binary_dilation(background, iterations=2)
    inner = connected_to(second, touching)
    if inner.mean() > 0.05:  # only a real inner box, not a thin garment outline
        background |= inner
    if kind == "black":
        # Background trapped between a sleeve and the body (not connected to the border).
        # Only large, pure-black pockets count, so small black logo details are kept.
        labels, n = ndimage.label(near_black & ~background)
        if n:
            sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
            darkness = ndimage.mean(rgb.max(axis=2), labels, range(1, n + 1))
            gaps = [i + 1 for i in range(n) if sizes[i] > GAP_MIN_SHARE * labels.size and darkness[i] < 6]
            background |= np.isin(labels, gaps)
        # Thin light slivers left along the cut edge (invisible on black, ugly on the light canvas).
        # Real white areas are thick; a sliver disappears after shrinking it by a few pixels.
        light = (rgb.min(axis=2) > 140) & ~background
        near_bg = ndimage.binary_dilation(background, iterations=3)
        labels, n = ndimage.label(light)
        if n:
            touching = set(np.unique(labels[near_bg & (labels > 0)]))
            core = ndimage.binary_erosion(light, iterations=FRINGE_MAX_WIDTH)
            core_sizes = ndimage.sum(core, labels, range(1, n + 1))
            slivers = [i + 1 for i in range(n) if (i + 1) in touching and core_sizes[i] == 0]
            background |= np.isin(labels, slivers)
    return Image.fromarray(np.where(background, 255, 0).astype(np.uint8))


def corner_kind(rgb: np.ndarray) -> str | None:
    corners = np.concatenate([rgb[:6, :6], rgb[:6, -6:], rgb[-6:, :6], rgb[-6:, -6:]]).reshape(-1, 3)
    mean = corners.mean(axis=0)
    if mean.max() < 30:
        return "black"
    if mean.min() > 240:
        return "white"
    return None


def clean(path: Path) -> str:
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im)
    kind = corner_kind(rgb)
    if kind is None:
        im.save(DST / path.name, quality=92)
        return "copied"

    bg = background_mask(rgb, kind)
    garment = ImageChops.invert(bg)
    if kind == "black":
        garment = garment.filter(ImageFilter.MinFilter(3))  # trim the dark fringe
    if path.name in SMOOTH_OUTLINE:
        # Very jagged cut-outs: blur the outline and re-threshold it, which rounds off stair-step edges.
        r = SMOOTH_OUTLINE[path.name]
        garment = garment.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v >= 128 else 0)
    alpha = garment.filter(ImageFilter.GaussianBlur(1.1))  # smooth the jagged edge

    # Soft drop shadow so light garments still stand out on the light canvas.
    shadow = garment.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.22))
    canvas = Image.new("RGB", im.size, CANVAS)
    canvas.paste(Image.new("RGB", im.size, (120, 120, 120)), (0, 6), shadow)
    canvas.paste(im, (0, 0), alpha)

    # Center on a square canvas with a little breathing room.
    box = garment.getbbox() or (0, 0, *im.size)
    cropped = canvas.crop(box)
    side = int(max(cropped.size) * 1.12)
    square = Image.new("RGB", (side, side), CANVAS)
    square.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2))
    square = square.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    square.save(DST / path.name, quality=92)
    return f"cleaned ({kind} background)"


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for path in sorted(SRC.glob("*.jpg")):
        if path.name in KEEP_ORIGINAL:
            (DST / path.name).unlink(missing_ok=True)
            result = "kept original (on the keep list)"
            counts[result] = counts.get(result, 0) + 1
            continue
        result = clean(path)
        counts[result] = counts.get(result, 0) + 1
    for result, n in counts.items():
        print(f"{n:3d}  {result}")
    print(f"Saved to {DST}")


if __name__ == "__main__":
    main()
