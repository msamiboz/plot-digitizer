#!/usr/bin/env python3
"""
Plot Digitizer — interactive app to extract time-series data from
TCMB inflation report chart images.

Usage:
    python app.py                        # opens pictures/ next to this script's parent dir
    python app.py /path/to/pictures/     # custom image folder
"""

import os
import sys
import glob
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pandas as pd
from PIL import Image, ImageTk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from extractor import extract_median, build_calibration, pixel_to_series

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ZOOM_CROP = 40          # half-size of the crop region in image pixels (~3.75x mag)
ZOOM_DISPLAY = 300      # display size of the zoom panel (pixels)
STEP_LABELS = {
    0: "Step 1 / 5 — Click two Y-axis reference points",
    1: "Step 2 / 5 — Click two X-axis reference points",
    2: "Step 3 / 5 — Click a point to pick the target color",
    3: "Step 4 / 5 — Click upper then lower vertical bound for median region",
    4: "Step 5 / 5 — Review extraction.  Save & Next or adjust.",
}


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class PlotDigitizer(tk.Tk):
    def __init__(self, image_dir: str, output_dir: str):
        super().__init__()
        self.title("Plot Digitizer")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.image_paths = sorted(glob.glob(os.path.join(image_dir, "*.png")))
        if not self.image_paths:
            messagebox.showerror("No images", f"No .png files found in\n{image_dir}")
            self.destroy()
            return

        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.img_index = 0
        self.pil_img = None
        self.img_array = None

        # Calibration state
        self._reset_state()

        self._build_ui()
        self._load_image()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _reset_state(self):
        self.step = 0
        self.y_clicks = []      # [(px_x, px_y), ...]
        self.x_clicks = []
        self.color_click = None  # (px_x, px_y)
        self.bound_clicks = []   # [(px_x, px_y), ...]
        self.target_color = None
        self.extracted = False
        self.last_unique_x = None
        self.last_smooth_y = None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Top status bar
        self.status_var = tk.StringVar(value="Loading...")
        status_bar = ttk.Label(self, textvariable=self.status_var,
                               font=("Helvetica", 13, "bold"),
                               anchor="w", padding=(8, 4))
        status_bar.pack(fill="x")

        # Horizontal pane: main canvas | zoom panel
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)

        # --- Main image canvas (matplotlib) ---
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_axis_off()
        self.canvas = FigureCanvasTkAgg(self.fig, master=pane)
        self.canvas_widget = self.canvas.get_tk_widget()
        pane.add(self.canvas_widget, weight=3)

        # --- Zoom panel (Tk Canvas for raw pixel zoom) ---
        zoom_frame = ttk.LabelFrame(pane, text="Zoom", padding=4)
        pane.add(zoom_frame, weight=1)
        self.zoom_canvas = tk.Canvas(zoom_frame, width=ZOOM_DISPLAY,
                                     height=ZOOM_DISPLAY, bg="gray20")
        self.zoom_canvas.pack()

        # Coordinate readout below zoom
        self.coord_var = tk.StringVar(value="x=— y=—")
        ttk.Label(zoom_frame, textvariable=self.coord_var,
                  font=("Courier", 11)).pack(pady=(4, 0))
        self.pixel_color_var = tk.StringVar(value="RGB: —")
        ttk.Label(zoom_frame, textvariable=self.pixel_color_var,
                  font=("Courier", 11)).pack()

        # Color swatch
        self.swatch_canvas = tk.Canvas(zoom_frame, width=60, height=30,
                                       bg="gray50", highlightthickness=1)
        self.swatch_canvas.pack(pady=(4, 2))
        ttk.Label(zoom_frame, text="Picked color ↑",
                  font=("Helvetica", 9)).pack()

        # --- Input panel ---
        input_frame = ttk.Frame(self, padding=6)
        input_frame.pack(fill="x")

        # Y calibration
        r = ttk.Frame(input_frame); r.pack(fill="x", pady=2)
        ttk.Label(r, text="Y1 value:").pack(side="left")
        self.y1_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.y1_var, width=10).pack(side="left", padx=(2, 12))
        ttk.Label(r, text="Y2 value:").pack(side="left")
        self.y2_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.y2_var, width=10).pack(side="left", padx=(2, 12))

        # X calibration
        ttk.Label(r, text="X1 date:").pack(side="left")
        self.x1_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.x1_var, width=12).pack(side="left", padx=(2, 12))
        ttk.Label(r, text="X2 date:").pack(side="left")
        self.x2_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.x2_var, width=12).pack(side="left", padx=(2, 12))

        # Tolerance
        ttk.Label(r, text="Tolerance:").pack(side="left")
        self.tol_var = tk.StringVar(value="15")
        ttk.Entry(r, textvariable=self.tol_var, width=5).pack(side="left", padx=(2, 0))

        # --- Button bar ---
        btn_frame = ttk.Frame(self, padding=6)
        btn_frame.pack(fill="x")

        self.undo_btn = ttk.Button(btn_frame, text="Undo Last Click",
                                   command=self._undo_click)
        self.undo_btn.pack(side="left", padx=4)

        self.confirm_btn = ttk.Button(btn_frame, text="Confirm Step",
                                      command=self._confirm_step)
        self.confirm_btn.pack(side="left", padx=4)

        self.extract_btn = ttk.Button(btn_frame, text="Run Extraction",
                                      command=self._run_extraction)
        self.extract_btn.pack(side="left", padx=4)

        self.save_btn = ttk.Button(btn_frame, text="Save && Next",
                                   command=self._save_and_next)
        self.save_btn.pack(side="left", padx=4)

        self.skip_btn = ttk.Button(btn_frame, text="Skip",
                                   command=self._skip_image)
        self.skip_btn.pack(side="left", padx=4)

        self.reset_btn = ttk.Button(btn_frame, text="Reset Image",
                                    command=self._reset_image)
        self.reset_btn.pack(side="left", padx=4)

        # Progress label on right side
        self.progress_var = tk.StringVar()
        ttk.Label(btn_frame, textvariable=self.progress_var,
                  font=("Helvetica", 11)).pack(side="right", padx=8)

        # Event bindings
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

        self._update_buttons()

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------
    def _load_image(self):
        path = self.image_paths[self.img_index]
        self.pil_img = Image.open(path).convert("RGB")
        self.img_array = np.array(self.pil_img)

        self._reset_state()
        self._redraw_image()
        self._update_status()
        self._update_buttons()
        self._clear_inputs()

        fname = os.path.basename(path)
        total = len(self.image_paths)
        self.progress_var.set(f"{fname}  ({self.img_index + 1} / {total})")
        self.title(f"Plot Digitizer — {fname}")

    def _clear_inputs(self):
        self.y1_var.set("")
        self.y2_var.set("")
        self.x1_var.set("")
        self.x2_var.set("")
        self.tol_var.set("15")
        self.swatch_canvas.configure(bg="gray50")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _redraw_image(self):
        self.ax.clear()
        self.ax.imshow(self.img_array)
        self.ax.set_axis_off()
        self._draw_markers()
        self.fig.tight_layout(pad=0.5)
        self.canvas.draw_idle()

    def _draw_markers(self):
        marker_kw = dict(markersize=10, markeredgewidth=2, linestyle="none")
        for i, (x, y) in enumerate(self.y_clicks):
            self.ax.plot(x, y, marker="+", color="red", **marker_kw)
            self.ax.annotate(f"Y{i+1}", (x, y), color="red",
                             fontsize=9, fontweight="bold",
                             xytext=(8, -4), textcoords="offset points")
        for i, (x, y) in enumerate(self.x_clicks):
            self.ax.plot(x, y, marker="+", color="lime", **marker_kw)
            self.ax.annotate(f"X{i+1}", (x, y), color="lime",
                             fontsize=9, fontweight="bold",
                             xytext=(8, -4), textcoords="offset points")
        if self.color_click:
            cx, cy = self.color_click
            self.ax.plot(cx, cy, marker="o", color="cyan", **marker_kw)
        for i, (x, y) in enumerate(self.bound_clicks):
            self.ax.axhline(y=y, color="orange", linewidth=1.5, linestyle="--")

        if self.extracted and self.last_unique_x is not None:
            self.ax.plot(self.last_unique_x, self.last_smooth_y,
                         color="red", linewidth=2, label="Extracted median")
            self.ax.legend(loc="upper right", fontsize=8)

    # ------------------------------------------------------------------
    # Zoom panel
    # ------------------------------------------------------------------
    def _update_zoom(self, img_x, img_y):
        if self.pil_img is None:
            return
        w, h = self.pil_img.size
        ix, iy = int(round(img_x)), int(round(img_y))

        left = max(ix - ZOOM_CROP, 0)
        upper = max(iy - ZOOM_CROP, 0)
        right = min(ix + ZOOM_CROP, w)
        lower = min(iy + ZOOM_CROP, h)

        crop = self.pil_img.crop((left, upper, right, lower))
        crop_w, crop_h = crop.size

        # Compute crosshair position accounting for asymmetric crops at edges
        scale_x = ZOOM_DISPLAY / crop_w if crop_w else 1
        scale_y = ZOOM_DISPLAY / crop_h if crop_h else 1
        cx = int((ix - left) * scale_x)
        cy = int((iy - upper) * scale_y)

        crop = crop.resize((ZOOM_DISPLAY, ZOOM_DISPLAY), Image.NEAREST)
        self._zoom_photo = ImageTk.PhotoImage(crop)
        self.zoom_canvas.delete("all")
        self.zoom_canvas.create_image(0, 0, anchor="nw", image=self._zoom_photo)

        arm = 15
        self.zoom_canvas.create_line(cx - arm, cy, cx + arm, cy, fill="red", width=1)
        self.zoom_canvas.create_line(cx, cy - arm, cx, cy + arm, fill="red", width=1)

        self.coord_var.set(f"x={ix}  y={iy}")

        if 0 <= iy < h and 0 <= ix < w:
            r, g, b = self.img_array[iy, ix]
            self.pixel_color_var.set(f"RGB: ({r}, {g}, {b})")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_motion(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        # Throttle zoom updates (~30 fps)
        now = self.tk.call("clock", "milliseconds")
        if hasattr(self, "_last_zoom_ms") and (now - self._last_zoom_ms) < 33:
            return
        self._last_zoom_ms = now
        self._update_zoom(event.xdata, event.ydata)

    def _on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        ix = int(round(event.xdata))
        iy = int(round(event.ydata))

        if self.step == 0:
            if len(self.y_clicks) < 2:
                self.y_clicks.append((ix, iy))
                self._redraw_image()
                if len(self.y_clicks) == 2:
                    self._update_status("  ✓ Two Y points picked. Enter values and Confirm.")
        elif self.step == 1:
            if len(self.x_clicks) < 2:
                self.x_clicks.append((ix, iy))
                self._redraw_image()
                if len(self.x_clicks) == 2:
                    self._update_status("  ✓ Two X points picked. Enter dates and Confirm.")
        elif self.step == 2:
            self.color_click = (ix, iy)
            h, w = self.img_array.shape[:2]
            if 0 <= iy < h and 0 <= ix < w:
                r, g, b = self.img_array[iy, ix]
                self.target_color = (int(r), int(g), int(b))
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                self.swatch_canvas.configure(bg=hex_color)
            self._redraw_image()
            self._update_status(f"  ✓ Color picked: RGB{self.target_color}. Confirm to continue.")
        elif self.step == 3:
            if len(self.bound_clicks) < 2:
                self.bound_clicks.append((ix, iy))
                self._redraw_image()
                if len(self.bound_clicks) == 2:
                    self._update_status("  ✓ Bounds set. Confirm to run extraction.")

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------
    def _undo_click(self):
        if self.step == 0 and self.y_clicks:
            self.y_clicks.pop()
        elif self.step == 1 and self.x_clicks:
            self.x_clicks.pop()
        elif self.step == 2:
            self.color_click = None
            self.target_color = None
            self.swatch_canvas.configure(bg="gray50")
        elif self.step == 3 and self.bound_clicks:
            self.bound_clicks.pop()
        self._redraw_image()
        self._update_status()

    def _confirm_step(self):
        if self.step == 0:
            if len(self.y_clicks) != 2:
                messagebox.showwarning("Y calibration",
                                       "Click exactly two Y-axis reference points first.")
                return
            try:
                v1 = float(self.y1_var.get())
                v2 = float(self.y2_var.get())
            except ValueError:
                messagebox.showwarning("Y calibration",
                                       "Enter numeric values for Y1 and Y2.")
                return
            self.step = 1

        elif self.step == 1:
            if len(self.x_clicks) != 2:
                messagebox.showwarning("X calibration",
                                       "Click exactly two X-axis reference points first.")
                return
            d1 = self.x1_var.get().strip()
            d2 = self.x2_var.get().strip()
            if not d1 or not d2:
                messagebox.showwarning("X calibration",
                                       "Enter dates for X1 and X2 (e.g. 2005-03).")
                return
            try:
                from extractor import _parse_date
                _parse_date(d1)
                _parse_date(d2)
            except ValueError as e:
                messagebox.showwarning("X calibration", str(e))
                return
            self.step = 2

        elif self.step == 2:
            if self.target_color is None:
                messagebox.showwarning("Color pick",
                                       "Click a point on the region of interest first.")
                return
            self.step = 3

        elif self.step == 3:
            if len(self.bound_clicks) != 2:
                messagebox.showwarning("Vertical bounds",
                                       "Click upper and lower vertical bounds first.")
                return
            self._run_extraction()
            return

        self._update_status()
        self._update_buttons()

    def _run_extraction(self):
        if self.step < 3:
            messagebox.showinfo("Not ready", "Complete all calibration steps first.")
            return

        try:
            tol = int(self.tol_var.get())
        except ValueError:
            tol = 15

        y_rows = [c[1] for c in self.bound_clicks]
        y_min_px = min(y_rows)
        y_max_px = max(y_rows)

        unique_x, smooth_y = extract_median(
            self.img_array, self.target_color, tol, y_min_px, y_max_px
        )

        if len(unique_x) == 0:
            messagebox.showwarning("Extraction",
                                   "No pixels matched the selected color within bounds.\n"
                                   "Try a larger tolerance or different color.")
            return

        self.last_unique_x = unique_x
        self.last_smooth_y = smooth_y
        self.extracted = True
        self.step = 4
        self._redraw_image()
        self._update_status()
        self._update_buttons()

    def _save_and_next(self):
        if not self.extracted:
            messagebox.showinfo("Not ready", "Run extraction first.")
            return

        v1 = float(self.y1_var.get())
        v2 = float(self.y2_var.get())
        y_calib = ((self.y_clicks[0][1], v1), (self.y_clicks[1][1], v2))

        d1 = self.x1_var.get().strip()
        d2 = self.x2_var.get().strip()
        x_calib = ((self.x_clicks[0][0], d1), (self.x_clicks[1][0], d2))

        y_func, x_func = build_calibration(y_calib, x_calib)
        dates, values = pixel_to_series(
            self.last_unique_x, self.last_smooth_y, y_func, x_func
        )

        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        df = pd.DataFrame({"date": date_strs, "value": values})

        src_name = os.path.splitext(
            os.path.basename(self.image_paths[self.img_index])
        )[0]
        out_path = os.path.join(self.output_dir, f"{src_name}.csv")
        df.to_csv(out_path, index=False)

        messagebox.showinfo("Saved", f"Saved {len(df)} rows to\n{out_path}")
        self._advance()

    def _skip_image(self):
        self._advance()

    def _reset_image(self):
        self._load_image()

    def _advance(self):
        self.img_index += 1
        if self.img_index >= len(self.image_paths):
            messagebox.showinfo("Done", "All images processed!")
            self.destroy()
            return
        self._load_image()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _update_status(self, extra=""):
        label = STEP_LABELS.get(self.step, "")
        self.status_var.set(label + extra)

    def _update_buttons(self):
        can_undo = (
            (self.step == 0 and len(self.y_clicks) > 0) or
            (self.step == 1 and len(self.x_clicks) > 0) or
            (self.step == 2 and self.color_click is not None) or
            (self.step == 3 and len(self.bound_clicks) > 0)
        )
        self.undo_btn.configure(state="normal" if can_undo else "disabled")
        self.confirm_btn.configure(
            state="normal" if self.step < 4 else "disabled")
        self.extract_btn.configure(
            state="normal" if self.step >= 3 else "disabled")
        self.save_btn.configure(
            state="normal" if self.extracted else "disabled")

    def _on_close(self):
        self.quit()
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_pictures = os.path.join(script_dir, "..", "pictures")

    if len(sys.argv) > 1:
        image_dir = sys.argv[1]
    else:
        image_dir = default_pictures

    image_dir = os.path.abspath(image_dir)
    output_dir = os.path.join(script_dir, "output")

    app = PlotDigitizer(image_dir, output_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
