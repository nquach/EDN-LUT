# Greyscale LUT Image Processor

A Python script that applies a 1D lookup table (LUT) to greyscale images. It reads JPG/PNG files from a directory, maps pixel values through a user-defined LUT (loaded from a CSV), and writes the processed images to an output directory. Optional negative + horizontal flip is supported.

## Features

- **1D LUT application**: Maps 8-bit input levels (0–255) to new 8-bit output levels via a CSV-defined lookup table.
- **Linear interpolation**: The LUT is built from (input, output) samples in the CSV; values for integer inputs 0–255 are computed by linear interpolation, so the CSV does not need to contain exactly 256 evenly spaced rows.
- **Batch processing**: Process all JPG/PNG images in a single directory in one run.
- **Negative + flip**: Optional `--negative` flag inverts pixel values and flips each image left–right (e.g. for film negative workflow).

## Requirements

- Python 3.x
- [Pillow](https://pypi.org/project/Pillow/) (PIL) ≥ 10.0.0

## Installation

```bash
git clone <repository-url>
cd cursor_jpegLUT
pip install -r requirements.txt
```

## LUT CSV format

The LUT is defined in a CSV (or TSV) file with two columns:

| Column | Meaning |
|--------|--------|
| **Scan** | Input pixel value (can be float; used for interpolation). |
| **Idea** | Output pixel value (clamped to 0–255). |

- The script builds a 256-entry LUT: for each integer input `i` in 0..255, it finds the surrounding (Scan, Idea) pairs in the file and **linearly interpolates** to get the output. Inputs outside the Scan range use the first or last sample.
- Delimiter: tab or comma (auto-detected).
- Header row must contain exactly the names `Scan` and `Idea` (spelling and case matter).

Example (tab-separated):

```
Idea	Scan
0.00	4.44
1.00	4.91
2.00	5.38
...
255.00	235.68
```

The included `normalized.csv` is an example of this format.

## Usage

```bash
python apply_lut.py --input-dir <INPUT_DIR> --output-dir <OUTPUT_DIR> --lut <LUT_CSV>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--input-dir` | Yes | Directory containing input images (JPG/PNG). Only the top level is scanned. |
| `--output-dir` | Yes | Directory where processed images are saved. Created if it does not exist. Existing files with the same name are overwritten. |
| `--lut` | Yes | Path to the CSV/TSV file with columns `Scan` (input) and `Idea` (output). |
| `--negative` | No | If set, invert pixel values (negative image) and flip each image left–right. |
| `--extensions` | No | Comma-separated list of file extensions to process (default: `jpg,jpeg,png`). Case-insensitive. |

### Examples

Process all JPG/PNG in `./photos` with the included LUT and save to `./out`:

```bash
python apply_lut.py --input-dir ./photos --output-dir ./out --lut normalized.csv
```

Same, but also apply negative and left–right flip:

```bash
python apply_lut.py --input-dir ./photos --output-dir ./out --lut normalized.csv --negative
```

Process only PNG files:

```bash
python apply_lut.py --input-dir ./photos --output-dir ./out --lut normalized.csv --extensions png
```

## How it works

1. **Load LUT**: The script reads the CSV, interprets each row as (Scan = input, Idea = output), sorts by Scan, and builds a 256-entry table by linearly interpolating between samples for each integer input 0–255. Output values are clamped to [0, 255] and rounded.
2. **Process images**: For each image in the input directory (matching the chosen extensions), the script opens it with Pillow, converts to greyscale (`L` mode), and applies the LUT with `Image.point()`. If `--negative` is set, the LUT is first replaced by `255 - lut[i]` and the image is flipped left–right after the LUT.
3. **Save**: Processed images are written to the output directory with the same filename; JPG/JPEG inputs are saved as JPEG, PNG as PNG.

Colour images are converted to greyscale before the LUT is applied; only the intensity is remapped.

## Project structure

```
cursor_jpegLUT/
├── README.md          # This file
├── apply_lut.py       # Main script
├── requirements.txt  # Python dependencies (Pillow)
└── normalized.csv     # Example LUT (Scan = input, Idea = output)
```

## Errors and validation

- The script exits with an error if the input directory or LUT file does not exist.
- If the CSV is missing the `Idea` or `Scan` column, or contains invalid numeric values, a clear error is printed.
- If no images are found in the input directory, the script prints a message and exits without error.
- Processing failures (e.g. corrupt image) are reported and cause a non-zero exit.
