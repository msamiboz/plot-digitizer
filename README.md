# Plot Digitizer v1.0.0

A desktop GUI tool for extracting time-series data from chart images. Point-and-click to pick a color, calibrate axes, and the app computes the median path — converting pixels into real-world dates and values exported as CSV.

Built with Python, Tkinter, and matplotlib. Runs locally on macOS, Linux, and Windows.

## Features

- **Start page** — configure input/output folders, Y-axis scale, smoothing, and marker colors before launching.
- **Color-based region detection** — click anywhere on the chart to pick the target color. Configurable tolerance.
- **Optional vertical bounds** — constrain extraction to a sub-region, or skip to use the full image.
- **Interactive axis calibration** — click Y1/Y2 and X1/X2 reference points with repeating cycle (Y1→Y2→Y1→Y2…) so you can refine freely before confirming.
- **Run Extraction anytime** — available as soon as a color is picked; re-run whenever you adjust settings.
- **Smooth extraction** — optional moving-average post-processing to reduce spikes and volatility.
- **Linear or log Y-axis** — choose before starting; the calibration math adapts automatically.
- **Colorblind-friendly palette** — one-click preset, or pick custom colors for every marker, bound line, and crosshair.
- **Live zoom panel** — magnified view tracks your cursor with configurable crosshair color.
- **Global undo** — undo the last click at any step, including mid-cycle replacements.
- **Batch processing** — loads all image files from the input folder and processes them one by one.
- **CSV output** — each image produces a `date,value` CSV file in the output folder.

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
python app.py                                # launch start page
python app.py /path/to/images/               # pre-fill input folder
python app.py /path/to/images/ /path/to/out/ # pre-fill both folders
```

## Workflow

The start page lets you configure folders and settings, then launches the digitizer.

For each image the app guides you through 5 steps:

| Step | Action | What to do |
|------|--------|------------|
| 1 | **Pick color** | Click on the colored region to extract. Run Extraction becomes available. |
| 2 | **Set bounds** | Click upper and lower boundaries (optional — Confirm to skip and use full image). |
| 3 | **Y-axis calibration** | Click Y1 and Y2 reference points (cycle repeats). Enter their numeric values. |
| 4 | **X-axis calibration** | Click X1 and X2 reference points (cycle repeats). Enter their dates. |
| 5 | **Review & save** | A red median line overlays the image. Save & Next or adjust. |

## Controls

| Button | Description |
|--------|-------------|
| **Undo Last Click** | Remove the most recent click in the current step |
| **Confirm Step** | Lock in the current step and advance |
| **Run Extraction** | Run (or re-run) extraction with current color, bounds, and tolerance |
| **Save & Next** | Save CSV and load the next image |
| **Skip** | Skip the current image without saving |
| **Reset Image** | Restart all steps for the current image |
| **Back to Start** | Return to the start page |

## Start Page Settings

| Setting | Options | Default |
|---------|---------|---------|
| **Y-axis scale** | Linear / Log | Linear |
| **Smooth extraction** | On / Off | Off |
| **Marker colors** | Default / Colorblind-friendly / Custom per marker | Default |

## Output

CSV format:

```csv
date,value
2005-03-01,8.0
2005-04-02,7.8
...
```

## Project Structure

```
plot_digitizer/
  app.py             # Main GUI (start page + digitizer)
  extractor.py       # Median extraction and calibration logic
  requirements.txt   # Python dependencies
  output/            # Generated CSV files (git-ignored)
```

## License

MIT License. See [LICENSE](LICENSE) for details.
