# Plot Digitizer

A desktop GUI tool for extracting time-series data from chart images. Point-and-click to calibrate axes, select a colored region, and the app computes the median path — converting pixels into real-world dates and values exported as CSV.

Built with Python, Tkinter, and matplotlib. Runs locally on macOS, Linux, and Windows.

## Features

- **Interactive axis calibration** — click two Y-axis and two X-axis reference points, enter their known values/dates, and the app builds a linear pixel-to-real mapping.
- **Color-based region detection** — click anywhere on the chart region you want to extract (e.g., a shaded forecast band). The app matches that color across the image using configurable tolerance.
- **Vertical bounds** — set upper and lower pixel limits to exclude legends, titles, or other chart elements that share the target color.
- **Median extraction** — computes the median y-coordinate of matched pixels at each x-column, fills holes, and smooths the result with a Savitzky-Golay filter.
- **Live zoom panel** — a magnified view (~4x) tracks your cursor in real time, showing pixel-level detail so you can precisely click on axis gridlines and tick marks.
- **Batch processing** — loads all `.png` images from a folder, processes them one by one, with Skip and Reset controls.
- **Undo support** — undo the last click at any calibration step before confirming.
- **CSV output** — each image produces a `date,value` CSV file saved to the `output/` directory.

## Requirements

- Python 3.9+
- macOS, Linux, or Windows (with Tkinter support)

## Installation

```bash
git clone https://github.com/msamiboz/plot-digitizer.git
cd plot-digitizer
pip install -r requirements.txt
```

## Usage

```bash
# Default: loads .png images from ../pictures/ relative to app.py
python app.py

# Custom image folder
python app.py /path/to/your/chart/images/
```

## Workflow

The app guides you through 5 steps for each image:

| Step | Action | What to do |
|------|--------|------------|
| 1 | **Y-axis calibration** | Click two points on known Y-axis gridlines. Enter their numeric values (e.g., `0` and `10`) in the Y1/Y2 fields. Click **Confirm Step**. |
| 2 | **X-axis calibration** | Click two points on known X-axis tick marks. Enter their dates (e.g., `2005-03` and `2007-02`) in the X1/X2 fields. Click **Confirm Step**. |
| 3 | **Color pick** | Click on the colored region you want to extract. A color swatch updates in the zoom panel. Adjust **Tolerance** if needed (default: 15). Click **Confirm Step**. |
| 4 | **Vertical bounds** | Click an upper and lower boundary to limit the extraction area. Click **Confirm Step** to run extraction. |
| 5 | **Review & save** | A red median line is overlaid on the image. If it looks correct, click **Save & Next**. Otherwise, adjust tolerance and click **Run Extraction** again, or **Reset Image** to start over. |

## Controls

| Button | Description |
|--------|-------------|
| **Undo Last Click** | Remove the most recent click in the current step |
| **Confirm Step** | Lock in the current step and advance to the next |
| **Run Extraction** | Run (or re-run) the median extraction with current settings |
| **Save & Next** | Save CSV to `output/` and load the next image |
| **Skip** | Skip the current image without saving |
| **Reset Image** | Restart all steps for the current image |

## Zoom Panel

The right-side panel shows a magnified view centered on your cursor. It displays:
- Pixel coordinates (`x`, `y`)
- RGB values at the cursor position
- A color swatch of the picked color (after Step 3)

Use this to precisely align clicks with axis gridlines.

## Output

Each processed image produces a CSV in the `output/` directory:

```
output/
  Inf_report_06_1.csv
  Inf_report_06_2.csv
  ...
```

CSV format:

```csv
date,value
2005-03-01,8.0
2005-04-02,7.8
...
2007-02-01,4.5
```

## Project Structure

```
plot_digitizer/
  app.py             # Main GUI application
  extractor.py       # Median extraction and calibration logic
  requirements.txt   # Python dependencies
  output/            # Generated CSV files (git-ignored)
```

## License

MIT License. See [LICENSE](LICENSE) for details.
