#!/usr/bin/env python3
"""
Utility to remove a small tag/serial text located at the top-right corner
of an image by covering it with a background-colored rectangle.

Default rectangle is sized for small corner tags like "#01409" seen on
clean white backgrounds. You can override the rectangle via --rect using
normalized coordinates (0..1) as: x1,y1,x2,y2 relative to image width/height.

Example:
  python3 remove_top_right_tag.py input.jpg output.jpg
  python3 remove_top_right_tag.py input.jpg output.jpg --rect "0.78,0.02,0.99,0.12"
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Tuple

from PIL import Image, ImageDraw


@dataclass
class NormalizedRect:
    """Rectangle with coordinates normalized to [0, 1]."""

    left: float
    top: float
    right: float
    bottom: float

    def to_pixels(self, width: int, height: int) -> Tuple[int, int, int, int]:
        left_px = max(0, min(width, int(round(self.left * width))))
        top_px = max(0, min(height, int(round(self.top * height))))
        right_px = max(0, min(width, int(round(self.right * width))))
        bottom_px = max(0, min(height, int(round(self.bottom * height))))
        # Ensure proper ordering
        left_px, right_px = min(left_px, right_px), max(left_px, right_px)
        top_px, bottom_px = min(top_px, bottom_px), max(top_px, bottom_px)
        return left_px, top_px, right_px, bottom_px


def parse_normalized_rect(rect_str: str) -> NormalizedRect:
    parts = [p.strip() for p in rect_str.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "--rect must be 'left,top,right,bottom' with four comma-separated numbers"
        )
    try:
        left, top, right, bottom = [float(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("--rect values must be floats in [0,1]")
    for value in (left, top, right, bottom):
        if not (0.0 <= value <= 1.0):
            raise argparse.ArgumentTypeError("--rect values must be within [0,1]")
    return NormalizedRect(left, top, right, bottom)


def compute_fill_color(image: Image.Image, box: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
    """
    Compute a reasonable background color by sampling a thin border just
    outside the target rectangle. Falls back to white if sampling fails.
    """
    try:
        width, height = image.size
        left, top, right, bottom = box

        # Define a sampling ring around the box
        margin = max(1, min(width, height) // 200)  # ~0.5% of smaller side

        # Expand outward for sampling (clamped)
        s_left = max(0, left - margin)
        s_top = max(0, top - margin)
        s_right = min(width, right + margin)
        s_bottom = min(height, bottom + margin)

        # Regions: top, bottom, left, right borders around the box
        samples = []
        if s_top < top:
            samples.append(image.crop((s_left, s_top, s_right, top)))
        if bottom < s_bottom:
            samples.append(image.crop((s_left, bottom, s_right, s_bottom)))
        if s_left < left:
            samples.append(image.crop((s_left, top, left, bottom)))
        if right < s_right:
            samples.append(image.crop((right, top, s_right, bottom)))

        pixels = []
        for region in samples:
            if region.size[0] == 0 or region.size[1] == 0:
                continue
            region_rgb = region.convert("RGB")
            pixels.extend(region_rgb.getdata())

        if not pixels:
            return (255, 255, 255)

        # Use median color for robustness to outliers
        rs = sorted(p[0] for p in pixels)
        gs = sorted(p[1] for p in pixels)
        bs = sorted(p[2] for p in pixels)
        mid = len(pixels) // 2
        return (rs[mid], gs[mid], bs[mid])
    except Exception:
        return (255, 255, 255)


def cover_top_right_tag(
    input_path: str,
    output_path: str,
    rect: NormalizedRect,
    quality: int = 95,
) -> None:
    image = Image.open(input_path)
    image_rgb = image.convert("RGB")

    width, height = image_rgb.size
    box = rect.to_pixels(width, height)

    fill_color = compute_fill_color(image_rgb, box)

    draw = ImageDraw.Draw(image_rgb)
    draw.rectangle(box, fill=fill_color)

    # Preserve format if possible
    save_kwargs = {}
    fmt = (image.format or "JPEG").upper()
    if fmt in {"JPEG", "JPG"}:
        save_kwargs.update({"quality": quality, "subsampling": 2, "optimize": True})
    image_rgb.save(output_path, format=fmt, **save_kwargs)


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove a small top-right tag from an image by covering it."
    )
    parser.add_argument("input", help="Path to input image file")
    parser.add_argument("output", help="Path to write the cleaned image")
    parser.add_argument(
        "--rect",
        type=parse_normalized_rect,
        default=NormalizedRect(0.74, 0.02, 0.99, 0.12),
        help=(
            "Normalized rectangle 'l,t,r,b' for the area to cover. "
            "Defaults to a small top-right region suitable for corner tags."
        ),
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality when saving JPEG output (default: 95)",
    )
    return parser


def main() -> None:
    args = build_argparser().parse_args()
    cover_top_right_tag(
        input_path=args.input,
        output_path=args.output,
        rect=args.rect,
        quality=args.quality,
    )


if __name__ == "__main__":
    main()

