#!/usr/bin/env python3
"""
Apply a 1D lookup table (LUT) to greyscale images in a directory.

Reads JPG/PNG images from a user-defined input directory, applies a LUT
loaded from a CSV file (columns: Scan = input level, Idea = output value).
Output for each integer input 0-255 is computed via linear interpolation.
Use --negative to invert the output (negative image) and flip the image left-right.
"""

import argparse
import colorsys
import csv
import sys
from pathlib import Path

from PIL import Image


def load_lut(csv_path: Path) -> list[int]:
    """Load a 256-entry LUT from a CSV with 'Scan' (input) and 'Idea' (output). Uses linear interpolation."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        sample = f.read(4096)
    f = open(csv_path, newline="", encoding="utf-8")
    try:
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        except csv.Error:
            dialect = csv.excel_tab
        reader = csv.DictReader(f, dialect=dialect)
        if reader.fieldnames is None or "Idea" not in reader.fieldnames or "Scan" not in reader.fieldnames:
            raise ValueError("CSV must have columns 'Idea' and 'Scan'")
        rows = list(reader)
    finally:
        f.close()

    # Parse (scan=input, idea=output) pairs; clamp idea to [0, 255]
    pairs: list[tuple[float, float]] = []
    for row in rows:
        try:
            scan = float(row["Scan"].strip())
            idea = float(row["Idea"].strip())
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid row in CSV: {row}") from e
        idea = max(0.0, min(255.0, idea))
        pairs.append((scan, idea))

    if not pairs:
        raise ValueError("CSV has no data rows")

    pairs.sort(key=lambda p: p[0])
    s_min, o_first = pairs[0][0], pairs[0][1]
    s_max, o_last = pairs[-1][0], pairs[-1][1]

    # For each integer input i in 0..255, interpolate output
    lut: list[int] = []
    for i in range(256):
        if i <= s_min:
            out_val = o_first
        elif i >= s_max:
            out_val = o_last
        elif len(pairs) == 1:
            out_val = o_first
        else:
            # Find consecutive (s0, o0) and (s1, o1) such that s0 <= i <= s1
            for j in range(1, len(pairs)):
                s0, o0 = pairs[j - 1][0], pairs[j - 1][1]
                s1, o1 = pairs[j][0], pairs[j][1]
                if s1 >= i:
                    if s1 == s0:
                        out_val = o0
                    else:
                        out_val = o0 + (o1 - o0) * (i - s0) / (s1 - s0)
                    break
            else:
                out_val = o_last
        out_val = max(0.0, min(255.0, out_val))
        lut.append(round(out_val))
    return lut


def collect_images(input_dir: Path, extensions: set[str]) -> list[Path]:
    """Return paths of files whose suffix (lower) is in extensions (single-level)."""
    paths: list[Path] = []
    ext_lower = {e.lower().lstrip(".") for e in extensions}
    for p in input_dir.iterdir():
        if p.is_file() and p.suffix.lower().lstrip(".") in ext_lower:
            paths.append(p)
    return sorted(paths)


def scale_to_full_range(img: Image.Image) -> Image.Image:
    """Scale pixel values to the full range 0-255 (min -> 0, max -> 255)."""
    pixels = list(img.get_flattened_data())
    min_val = min(pixels)
    max_val = max(pixels)
    if max_val == min_val:
        # Constant image: set all to 0 (or leave unchanged; 0 keeps range [0,255])
        scaled = [0] * len(pixels)
    else:
        scale = 255.0 / (max_val - min_val)
        scaled = [round((p - min_val) * scale) for p in pixels]
    out_img = Image.new("L", img.size)
    out_img.putdata(scaled)
    return out_img


def apply_hsv_tint(img: Image.Image, h: float, s: float, v_scale: float) -> Image.Image:
    """Convert greyscale image (L) to RGB using fixed H and S; pixel value drives V scaled by v_scale. h,s,v_scale in [0,1]."""
    pixels = list(img.get_flattened_data())
    rgb_pixels: list[tuple[int, int, int]] = []
    for L in pixels:
        v = (L / 255.0) * v_scale
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        rgb_pixels.append((round(r * 255), round(g * 255), round(b * 255)))
    out = Image.new("RGB", img.size)
    out.putdata(rgb_pixels)
    return out


def process_image(path: Path, lut: list[int], output_dir: Path, flip_left_right: bool = False, hsv: tuple[float, float, float] | None = None) -> None:
    """Load image, convert to greyscale, scale to 0-255, apply LUT, optionally flip left-right, optionally apply HSV tint, save to output_dir (same filename)."""
    img = Image.open(path).convert("L")
    img = scale_to_full_range(img)
    out = img.point(lut, mode="L")
    if flip_left_right:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    if hsv is not None:
        h, s, v_scale = hsv
        out = apply_hsv_tint(out, h, s, v_scale)
    out_path = output_dir / path.name
    # Preserve format: JPG/JPEG -> JPEG, PNG -> PNG
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        out.save(out_path, format="JPEG")
    else:
        out.save(out_path, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a 1D LUT to greyscale JPG/PNG images from a directory."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing input images (JPG/PNG)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where processed images will be saved (created if missing)",
    )
    parser.add_argument(
        "--lut",
        type=Path,
        required=True,
        help="Path to CSV LUT with columns 'Scan' (input) and 'Idea' (output)",
    )
    parser.add_argument(
        "--negative",
        action="store_true",
        help="Invert output pixel values (negative) and flip image left-right",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        default="jpg,jpeg,png",
        help="Comma-separated file extensions to process (default: jpg,jpeg,png)",
    )
    parser.add_argument(
        "--hsv",
        type=str,
        default=None,
        metavar="H,S,V",
        help="Tint output to HSV color: H 0-360, S 0-100, V 0-100 (V scales luminance)",
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Error: input directory does not exist: {args.input_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.lut.is_file():
        print(f"Error: LUT file does not exist: {args.lut}", file=sys.stderr)
        sys.exit(1)

    try:
        lut = load_lut(args.lut)
    except ValueError as e:
        print(f"Error loading LUT: {e}", file=sys.stderr)
        sys.exit(1)

    if args.negative:
        lut = [255 - v for v in lut]

    hsv_tuple: tuple[float, float, float] | None = None
    if args.hsv is not None:
        parts = [p.strip() for p in args.hsv.split(",")]
        if len(parts) != 3:
            print("Error: --hsv must be H,S,V (e.g. 30,100,100)", file=sys.stderr)
            sys.exit(1)
        try:
            h_deg = float(parts[0])
            s_pct = float(parts[1])
            v_pct = float(parts[2])
        except ValueError as e:
            print(f"Error: --hsv values must be numbers: {e}", file=sys.stderr)
            sys.exit(1)
        if not (0 <= h_deg <= 360):
            print("Error: --hsv H must be in [0, 360]", file=sys.stderr)
            sys.exit(1)
        if not (0 <= s_pct <= 100) or not (0 <= v_pct <= 100):
            print("Error: --hsv S and V must be in [0, 100]", file=sys.stderr)
            sys.exit(1)
        hsv_tuple = (h_deg / 360.0, s_pct / 100.0, v_pct / 100.0)

    extensions = {e.strip() for e in args.extensions.split(",") if e.strip()}
    images = collect_images(args.input_dir, extensions)

    if not images:
        print("No images found in input directory. Exiting.")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for path in images:
        try:
            process_image(path, lut, args.output_dir, flip_left_right=args.negative, hsv=hsv_tuple)
            print(path.name)
        except Exception as e:
            print(f"Error processing {path}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Processed {len(images)} image(s) -> {args.output_dir}")


if __name__ == "__main__":
    main()
