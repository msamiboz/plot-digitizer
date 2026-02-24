#!/usr/bin/env python3
"""
Plot Digitizer v1.0.0
Interactive desktop app to extract time-series data from chart images.

Usage:
    python app.py                                # launch start page
    python app.py /path/to/images/               # pre-fill input folder
    python app.py /path/to/images/ /path/to/out/ # pre-fill both folders
"""

import os
import sys
import glob
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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
ZOOM_CROP = 40
ZOOM_DISPLAY = 300

DEFAULT_COLORS = {
    "y1": "#FF0000",
    "y2": "#FF0000",
    "x1": "#00FF00",
    "x2": "#00FF00",
    "color_picker": "#00FFFF",
    "bounds": "#FF8800",
    "crosshair": "#FF0000",
}

COLORBLIND_COLORS = {
    "y1": "#0072B2",
    "y2": "#0072B2",
    "x1": "#E69F00",
    "x2": "#E69F00",
    "color_picker": "#CC79A7",
    "bounds": "#009E73",
    "crosshair": "#D55E00",
}

STEP_LABELS = {
    0: "Step 1 / 5 — Click on the chart to pick the target color",
    1: "Step 2 / 5 — Click upper & lower bounds (optional — Confirm to skip)",
    2: "Step 3 / 5 — Click Y-axis points (Y1, Y2 cycle). Enter values, then Confirm.",
    3: "Step 4 / 5 — Click X-axis points (X1, X2 cycle). Enter dates, then Confirm.",
    4: "Step 5 / 5 — Review extraction. Save & Next or adjust.",
}


# ═══════════════════════════════════════════════════════════════════════════
# Start Page
# ═══════════════════════════════════════════════════════════════════════════
class StartPage(ttk.Frame):
    """Welcome page shown before launching the digitizer."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        f = ttk.Frame(self)
        f.pack(expand=True)
        px = 30

        # ── Title ──
        ttk.Label(f, text="Plot Digitizer v1.0.0",
                  font=("Helvetica", 22, "bold")).pack(pady=(24, 6), padx=px)
        ttk.Label(f, text=(
            "Extract time-series data from chart images.\n"
            "Pick a color, set bounds, calibrate axes, and export as CSV."
        ), font=("Helvetica", 12), justify="center").pack(pady=(0, 16), padx=px)

        # ── Folders ──
        self._section(f, "Folders")

        row = ttk.Frame(f); row.pack(fill="x", padx=px, pady=3)
        ttk.Label(row, text="Input folder:", width=14, anchor="e").pack(side="left")
        self.input_var = tk.StringVar(value=self.app.settings.get("input_dir", ""))
        ttk.Entry(row, textvariable=self.input_var, width=52).pack(side="left", padx=4)
        ttk.Button(row, text="Browse", command=self._browse_input).pack(side="left")

        row = ttk.Frame(f); row.pack(fill="x", padx=px, pady=3)
        ttk.Label(row, text="Output folder:", width=14, anchor="e").pack(side="left")
        self.output_var = tk.StringVar(value=self.app.settings.get("output_dir", ""))
        ttk.Entry(row, textvariable=self.output_var, width=52).pack(side="left", padx=4)
        ttk.Button(row, text="Browse", command=self._browse_output).pack(side="left")

        # ── Workflow ──
        self._section(f, "Workflow Steps")
        steps = [
            "1.  Pick the target color on the chart",
            "2.  Set vertical bounds, optional",
            "3.  Calibrate Y-axis: click Y1, Y2 pairs",
            "4.  Calibrate X-axis: click X1, X2 pairs",
            "5.  Review the extracted median line — Save & Next",
        ]
        for s in steps:
            ttk.Label(f, text=s, font=("Helvetica", 11)).pack(
                anchor="w", padx=50, pady=1)

        # ── Settings + Start buttons ──
        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=px, pady=14)
        style = ttk.Style()
        style.configure("Start.TButton",
                        font=("Helvetica", 14, "bold"), padding=(24, 10))
        style.configure("Settings.TButton",
                        font=("Helvetica", 12), padding=(16, 8))

        btn_row = ttk.Frame(f); btn_row.pack(pady=(0, 28))
        ttk.Button(btn_row, text="Settings",
                   command=self._open_settings,
                   style="Settings.TButton").pack(side="left", padx=8)
        ttk.Button(btn_row, text="Start Digitizer",
                   command=self._start,
                   style="Start.TButton").pack(side="left", padx=8)

    # ------------------------------------------------------------------
    @staticmethod
    def _section(parent, title):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=30, pady=10)
        ttk.Label(parent, text=title,
                  font=("Helvetica", 14, "bold")).pack(anchor="w", padx=30)

    def _browse_input(self):
        d = filedialog.askdirectory(title="Select input image folder")
        if d:
            self.input_var.set(d)

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.output_var.set(d)

    def _open_settings(self):
        self.app.settings["input_dir"] = self.input_var.get().strip()
        self.app.settings["output_dir"] = self.output_var.get().strip()
        self.app.show_settings()

    def _start(self):
        inp = self.input_var.get().strip()
        out = self.output_var.get().strip()
        if not inp:
            messagebox.showwarning("Input folder", "Select an input image folder.")
            return
        if not os.path.isdir(inp):
            messagebox.showwarning("Input folder", f"Folder not found:\n{inp}")
            return
        if not out:
            messagebox.showwarning("Output folder", "Select an output folder.")
            return

        self.app.settings.update({"input_dir": inp, "output_dir": out})
        self.app.show_digitizer()


# ═══════════════════════════════════════════════════════════════════════════
# Settings Page
# ═══════════════════════════════════════════════════════════════════════════
class SettingsPage(ttk.Frame):
    """Separate settings page opened from the start page."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        f = ttk.Frame(self)
        f.pack(expand=True)
        px = 30

        ttk.Label(f, text="Settings",
                  font=("Helvetica", 22, "bold")).pack(pady=(24, 16), padx=px)

        # ── Y-axis scale ──
        ttk.Label(f, text="Y-axis scale",
                  font=("Helvetica", 14, "bold")).pack(anchor="w", padx=px)
        row = ttk.Frame(f); row.pack(fill="x", padx=px, pady=(4, 12))
        self.y_scale_var = tk.StringVar(
            value=self.app.settings.get("y_axis_type", "linear"))
        ttk.Radiobutton(row, text="Linear",
                        variable=self.y_scale_var, value="linear").pack(
            side="left", padx=(0, 8))
        ttk.Radiobutton(row, text="Log",
                        variable=self.y_scale_var, value="log").pack(side="left")

        # ── Smooth extraction ──
        ttk.Label(f, text="Extraction smoothing",
                  font=("Helvetica", 14, "bold")).pack(anchor="w", padx=px)
        row = ttk.Frame(f); row.pack(fill="x", padx=px, pady=(4, 12))
        self.smooth_var = tk.BooleanVar(
            value=self.app.settings.get("smooth", False))
        ttk.Checkbutton(
            row,
            text="Smooth the extraction (moving average to reduce spikes / volatility)",
            variable=self.smooth_var,
        ).pack(side="left")

        # ── Color scheme ──
        ttk.Label(f, text="Color scheme",
                  font=("Helvetica", 14, "bold")).pack(anchor="w", padx=px)

        current_scheme = self.app.settings.get("color_scheme", "default")
        self.scheme_var = tk.StringVar(value=current_scheme)

        row = ttk.Frame(f); row.pack(fill="x", padx=px, pady=(4, 4))
        ttk.Radiobutton(row, text="Default",
                        variable=self.scheme_var, value="default",
                        command=self._update_preview).pack(side="left", padx=(0, 8))
        ttk.Radiobutton(row, text="Accessible (colorblind-friendly)",
                        variable=self.scheme_var, value="accessible",
                        command=self._update_preview).pack(side="left")

        # Preview swatches
        self.preview_frame = ttk.Frame(f)
        self.preview_frame.pack(fill="x", padx=px + 10, pady=(8, 16))
        self.swatch_widgets = {}
        self._update_preview()

        # ── Back button ──
        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=px, pady=10)
        style = ttk.Style()
        style.configure("Back.TButton",
                        font=("Helvetica", 12), padding=(16, 8))
        ttk.Button(f, text="Back", command=self._go_back,
                   style="Back.TButton").pack(pady=(0, 24))

    def _update_preview(self):
        for w in self.preview_frame.winfo_children():
            w.destroy()

        colors = (DEFAULT_COLORS if self.scheme_var.get() == "default"
                  else COLORBLIND_COLORS)
        labels = [
            ("Y markers", colors["y1"]),
            ("X markers", colors["x1"]),
            ("Color picker", colors["color_picker"]),
            ("Bound lines", colors["bounds"]),
            ("Crosshair", colors["crosshair"]),
        ]
        for label, clr in labels:
            row = ttk.Frame(self.preview_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", width=14, anchor="e").pack(side="left")
            sw = tk.Canvas(row, width=30, height=18, bg=clr, highlightthickness=1)
            sw.pack(side="left", padx=6)
            ttk.Label(row, text=clr, font=("Courier", 10)).pack(side="left")

    def _go_back(self):
        scheme = self.scheme_var.get()
        colors = dict(DEFAULT_COLORS if scheme == "default" else COLORBLIND_COLORS)
        self.app.settings.update({
            "y_axis_type": self.y_scale_var.get(),
            "smooth": self.smooth_var.get(),
            "color_scheme": scheme,
            "colors": colors,
        })
        self.app.show_start_page()


# ═══════════════════════════════════════════════════════════════════════════
# Plot Digitizer (main working view)
# ═══════════════════════════════════════════════════════════════════════════
class PlotDigitizer(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        self.colors = dict(app.settings["colors"])

        image_dir = self.settings["input_dir"]
        self.output_dir = self.settings["output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)

        exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff")
        self.image_paths = sorted(
            p for ext in exts
            for p in glob.glob(os.path.join(image_dir, ext))
        )
        if not self.image_paths:
            messagebox.showerror("No images",
                                 f"No image files found in\n{image_dir}")
            app.show_start_page()
            return

        self.img_index = 0
        self.pil_img = None
        self.img_array = None

        self._reset_state()
        self._build_ui()
        self._load_image()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _reset_state(self):
        self.step = 0
        self.color_click = None
        self.target_color = None
        self.bound_clicks = []
        self.y_clicks = []          # max 2 entries: [Y1, Y2]
        self.x_clicks = []          # max 2 entries: [X1, X2]
        self.y_click_counter = 0    # total Y clicks (for cycling)
        self.x_click_counter = 0
        self.extracted = False
        self.last_unique_x = None
        self.last_smooth_y = None
        self.undo_stack = []        # [(step, action, ...payload)]

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Status bar
        self.status_var = tk.StringVar(value="Loading…")
        ttk.Label(self, textvariable=self.status_var,
                  font=("Helvetica", 13, "bold"),
                  anchor="w", padding=(8, 4)).pack(fill="x")

        # Horizontal pane: image | zoom
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_axis_off()
        self.canvas = FigureCanvasTkAgg(self.fig, master=pane)
        self.canvas_widget = self.canvas.get_tk_widget()
        pane.add(self.canvas_widget, weight=3)

        zoom_frame = ttk.LabelFrame(pane, text="Zoom", padding=4)
        pane.add(zoom_frame, weight=1)
        self.zoom_canvas = tk.Canvas(zoom_frame, width=ZOOM_DISPLAY,
                                     height=ZOOM_DISPLAY, bg="gray20")
        self.zoom_canvas.pack()

        self.coord_var = tk.StringVar(value="x=—  y=—")
        ttk.Label(zoom_frame, textvariable=self.coord_var,
                  font=("Courier", 11)).pack(pady=(4, 0))
        self.pixel_color_var = tk.StringVar(value="RGB: —")
        ttk.Label(zoom_frame, textvariable=self.pixel_color_var,
                  font=("Courier", 11)).pack()

        self.swatch_canvas = tk.Canvas(zoom_frame, width=60, height=30,
                                       bg="gray50", highlightthickness=1)
        self.swatch_canvas.pack(pady=(4, 2))
        ttk.Label(zoom_frame, text="Picked color",
                  font=("Helvetica", 9)).pack()

        # ── Input fields ──
        inp = ttk.Frame(self, padding=6)
        inp.pack(fill="x")

        row = ttk.Frame(inp); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Y1 value:").pack(side="left")
        self.y1_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.y1_var, width=10).pack(
            side="left", padx=(2, 12))
        ttk.Label(row, text="Y2 value:").pack(side="left")
        self.y2_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.y2_var, width=10).pack(
            side="left", padx=(2, 12))

        ttk.Label(row, text="X1 date:").pack(side="left")
        self.x1_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.x1_var, width=12).pack(
            side="left", padx=(2, 12))
        ttk.Label(row, text="X2 date:").pack(side="left")
        self.x2_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.x2_var, width=12).pack(
            side="left", padx=(2, 12))

        ttk.Label(row, text="Tolerance:").pack(side="left")
        self.tol_var = tk.StringVar(value="15")
        ttk.Entry(row, textvariable=self.tol_var, width=5).pack(
            side="left", padx=(2, 0))

        # ── Button bar ──
        bf = ttk.Frame(self, padding=6)
        bf.pack(fill="x")

        self.undo_btn = ttk.Button(bf, text="Undo Last Click",
                                   command=self._undo_click)
        self.undo_btn.pack(side="left", padx=4)
        self.confirm_btn = ttk.Button(bf, text="Confirm Step",
                                      command=self._confirm_step)
        self.confirm_btn.pack(side="left", padx=4)
        self.extract_btn = ttk.Button(bf, text="Run Extraction",
                                      command=self._run_extraction)
        self.extract_btn.pack(side="left", padx=4)
        self.save_btn = ttk.Button(bf, text="Save && Next",
                                   command=self._save_and_next)
        self.save_btn.pack(side="left", padx=4)
        self.skip_btn = ttk.Button(bf, text="Skip",
                                   command=self._skip)
        self.skip_btn.pack(side="left", padx=4)
        self.reset_btn = ttk.Button(bf, text="Reset Image",
                                    command=self._reset_image)
        self.reset_btn.pack(side="left", padx=4)
        ttk.Button(bf, text="Back to Start",
                   command=self._back).pack(side="left", padx=4)

        self.progress_var = tk.StringVar()
        ttk.Label(bf, textvariable=self.progress_var,
                  font=("Helvetica", 11)).pack(side="right", padx=8)

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
        self._redraw()
        self._update_status()
        self._update_buttons()
        self._clear_inputs()

        fname = os.path.basename(path)
        self.progress_var.set(
            f"{fname}  ({self.img_index + 1} / {len(self.image_paths)})")
        self.app.title(f"Plot Digitizer — {fname}")

    def _clear_inputs(self):
        for v in (self.y1_var, self.y2_var, self.x1_var, self.x2_var):
            v.set("")
        self.tol_var.set("15")
        self.swatch_canvas.configure(bg="gray50")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _redraw(self):
        self.ax.clear()
        self.ax.imshow(self.img_array)
        self.ax.set_axis_off()
        self._draw_markers()
        self.fig.tight_layout(pad=0.5)
        self.canvas.draw_idle()

    def _draw_markers(self):
        c = self.colors
        kw = dict(markersize=10, markeredgewidth=2, linestyle="none")

        if self.color_click:
            self.ax.plot(*self.color_click, marker="o",
                         color=c["color_picker"], **kw)

        for _, by in self.bound_clicks:
            self.ax.axhline(y=by, color=c["bounds"],
                            linewidth=1.5, linestyle="--")

        for i, (x, y) in enumerate(self.y_clicks):
            clr = c["y1"] if i == 0 else c["y2"]
            self.ax.plot(x, y, marker="+", color=clr, **kw)
            self.ax.annotate(f"Y{i+1}", (x, y), color=clr,
                             fontsize=9, fontweight="bold",
                             xytext=(8, -4), textcoords="offset points")

        for i, (x, y) in enumerate(self.x_clicks):
            clr = c["x1"] if i == 0 else c["x2"]
            self.ax.plot(x, y, marker="+", color=clr, **kw)
            self.ax.annotate(f"X{i+1}", (x, y), color=clr,
                             fontsize=9, fontweight="bold",
                             xytext=(8, -4), textcoords="offset points")

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
        cw, ch = crop.size
        sx = ZOOM_DISPLAY / cw if cw else 1
        sy = ZOOM_DISPLAY / ch if ch else 1
        cx = int((ix - left) * sx)
        cy = int((iy - upper) * sy)

        crop = crop.resize((ZOOM_DISPLAY, ZOOM_DISPLAY), Image.NEAREST)
        self._zoom_photo = ImageTk.PhotoImage(crop)
        self.zoom_canvas.delete("all")
        self.zoom_canvas.create_image(0, 0, anchor="nw",
                                      image=self._zoom_photo)

        arm = 15
        ch_clr = self.colors["crosshair"]
        self.zoom_canvas.create_line(cx - arm, cy, cx + arm, cy,
                                     fill=ch_clr, width=1)
        self.zoom_canvas.create_line(cx, cy - arm, cx, cy + arm,
                                     fill=ch_clr, width=1)

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
        now = time.monotonic()
        if hasattr(self, "_last_zoom") and (now - self._last_zoom) < 0.033:
            return
        self._last_zoom = now
        self._update_zoom(event.xdata, event.ydata)

    def _on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        ix, iy = int(round(event.xdata)), int(round(event.ydata))

        # ── Step 0: color pick ──
        if self.step == 0:
            old_c, old_t = self.color_click, self.target_color
            self.color_click = (ix, iy)
            h, w = self.img_array.shape[:2]
            if 0 <= iy < h and 0 <= ix < w:
                r, g, b = self.img_array[iy, ix]
                self.target_color = (int(r), int(g), int(b))
                self.swatch_canvas.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
            self.undo_stack.append((0, "color", old_c, old_t))
            self._redraw()
            self._update_status(
                f"  Color: RGB{self.target_color}. Confirm or keep clicking.")
            self._update_buttons()

        # ── Step 1: bounds (max 2) ──
        elif self.step == 1:
            if len(self.bound_clicks) < 2:
                self.bound_clicks.append((ix, iy))
                self.undo_stack.append((1, "bound_add"))
                self._redraw()
                if len(self.bound_clicks) == 2:
                    self._update_status(
                        "  Bounds set. Confirm to continue.")
                else:
                    self._update_status(
                        "  Upper bound set. Click lower bound.")
                self._update_buttons()

        # ── Step 2: Y calibration (repeating Y1 Y2 cycle) ──
        elif self.step == 2:
            pos = self.y_click_counter % 2
            if pos < len(self.y_clicks):
                old = self.y_clicks[pos]
                self.y_clicks[pos] = (ix, iy)
                self.undo_stack.append((2, "y_replace", pos, old))
            else:
                self.y_clicks.append((ix, iy))
                self.undo_stack.append((2, "y_add", pos))
            self.y_click_counter += 1
            self._redraw()
            tag = f"Y{pos + 1}"
            if len(self.y_clicks) >= 2:
                self._update_status(
                    f"  {tag} updated. Enter values & Confirm, "
                    f"or keep clicking to adjust.")
            else:
                self._update_status(f"  {tag} set. Click Y{2 - pos} next.")
            self._update_buttons()

        # ── Step 3: X calibration (repeating X1 X2 cycle) ──
        elif self.step == 3:
            pos = self.x_click_counter % 2
            if pos < len(self.x_clicks):
                old = self.x_clicks[pos]
                self.x_clicks[pos] = (ix, iy)
                self.undo_stack.append((3, "x_replace", pos, old))
            else:
                self.x_clicks.append((ix, iy))
                self.undo_stack.append((3, "x_add", pos))
            self.x_click_counter += 1
            self._redraw()
            tag = f"X{pos + 1}"
            if len(self.x_clicks) >= 2:
                self._update_status(
                    f"  {tag} updated. Enter dates & Confirm, "
                    f"or keep clicking to adjust.")
            else:
                self._update_status(f"  {tag} set. Click X{2 - pos} next.")
            self._update_buttons()

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------
    def _undo_click(self):
        if not self.undo_stack or self.undo_stack[-1][0] != self.step:
            return
        entry = self.undo_stack.pop()
        action = entry[1]

        if action == "color":
            self.color_click = entry[2]
            self.target_color = entry[3]
            if self.target_color:
                r, g, b = self.target_color
                self.swatch_canvas.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
            else:
                self.swatch_canvas.configure(bg="gray50")

        elif action == "bound_add":
            if self.bound_clicks:
                self.bound_clicks.pop()

        elif action == "y_add":
            pos = entry[2]
            if len(self.y_clicks) > pos:
                self.y_clicks.pop()
            self.y_click_counter = max(0, self.y_click_counter - 1)

        elif action == "y_replace":
            pos, old = entry[2], entry[3]
            self.y_clicks[pos] = old
            self.y_click_counter = max(0, self.y_click_counter - 1)

        elif action == "x_add":
            pos = entry[2]
            if len(self.x_clicks) > pos:
                self.x_clicks.pop()
            self.x_click_counter = max(0, self.x_click_counter - 1)

        elif action == "x_replace":
            pos, old = entry[2], entry[3]
            self.x_clicks[pos] = old
            self.x_click_counter = max(0, self.x_click_counter - 1)

        self._redraw()
        self._update_status()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Confirm / advance
    # ------------------------------------------------------------------
    def _confirm_step(self):
        if self.step == 0:
            if self.target_color is None:
                messagebox.showwarning(
                    "Color", "Click on the region of interest first.")
                return
            self.step = 1

        elif self.step == 1:
            if len(self.bound_clicks) == 1:
                messagebox.showwarning(
                    "Bounds",
                    "Click a second bound, or Undo the first to skip bounds.")
                return
            self.step = 2

        elif self.step == 2:
            if len(self.y_clicks) < 2:
                messagebox.showwarning(
                    "Y calibration",
                    "Click at least Y1 and Y2 reference points.")
                return
            try:
                float(self.y1_var.get())
                float(self.y2_var.get())
            except ValueError:
                messagebox.showwarning(
                    "Y calibration", "Enter numeric values for Y1 and Y2.")
                return
            self.step = 3

        elif self.step == 3:
            if len(self.x_clicks) < 2:
                messagebox.showwarning(
                    "X calibration",
                    "Click at least X1 and X2 reference points.")
                return
            d1 = self.x1_var.get().strip()
            d2 = self.x2_var.get().strip()
            if not d1 or not d2:
                messagebox.showwarning(
                    "X calibration",
                    "Enter dates for X1 and X2 (e.g. 2005-03).")
                return
            try:
                from extractor import _parse_date
                _parse_date(d1)
                _parse_date(d2)
            except ValueError as e:
                messagebox.showwarning("X calibration", str(e))
                return
            self._run_extraction(advance=True)
            return

        self._update_status()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _run_extraction(self, advance=False):
        if self.target_color is None:
            messagebox.showinfo("Not ready", "Pick a color first.")
            return

        try:
            tol = int(self.tol_var.get())
        except ValueError:
            tol = 15

        h = self.img_array.shape[0]
        if len(self.bound_clicks) >= 2:
            rows = [c[1] for c in self.bound_clicks]
            y_min, y_max = min(rows), max(rows)
        else:
            y_min, y_max = 0, h - 1

        ux, sy = extract_median(
            self.img_array, self.target_color, tol, y_min, y_max,
            apply_smooth=self.settings.get("smooth", False),
        )
        if len(ux) == 0:
            messagebox.showwarning(
                "Extraction",
                "No pixels matched. Try a larger tolerance or different color.")
            return

        self.last_unique_x = ux
        self.last_smooth_y = sy
        self.extracted = True
        if advance:
            self.step = 4
        self._redraw()
        self._update_status()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Save / navigation
    # ------------------------------------------------------------------
    def _save_and_next(self):
        if not self.extracted:
            messagebox.showinfo("Not ready", "Run extraction first.")
            return
        if len(self.y_clicks) < 2 or len(self.x_clicks) < 2:
            messagebox.showwarning(
                "Calibration", "Complete Y and X calibration before saving.")
            return
        try:
            v1 = float(self.y1_var.get())
            v2 = float(self.y2_var.get())
        except ValueError:
            messagebox.showwarning("Values", "Enter numeric Y1 / Y2 values.")
            return
        d1 = self.x1_var.get().strip()
        d2 = self.x2_var.get().strip()
        if not d1 or not d2:
            messagebox.showwarning("Dates", "Enter X1 / X2 dates.")
            return

        y_scale = self.settings.get("y_axis_type", "linear")
        y_calib = ((self.y_clicks[0][1], v1), (self.y_clicks[1][1], v2))
        x_calib = ((self.x_clicks[0][0], d1), (self.x_clicks[1][0], d2))

        try:
            y_func, x_func = build_calibration(
                y_calib, x_calib, y_scale=y_scale)
        except ValueError as e:
            messagebox.showwarning("Calibration error", str(e))
            return

        dates, values = pixel_to_series(
            self.last_unique_x, self.last_smooth_y, y_func, x_func)

        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "value": values,
        })

        src = os.path.splitext(
            os.path.basename(self.image_paths[self.img_index]))[0]
        out_path = os.path.join(self.output_dir, f"{src}.csv")
        df.to_csv(out_path, index=False)

        messagebox.showinfo("Saved", f"Saved {len(df)} rows to\n{out_path}")
        self._advance()

    def _skip(self):
        self._advance()

    def _reset_image(self):
        self._load_image()

    def _back(self):
        self.app.show_start_page()

    def _advance(self):
        self.img_index += 1
        if self.img_index >= len(self.image_paths):
            messagebox.showinfo("Done", "All images processed!")
            self.app.show_start_page()
            return
        self._load_image()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _update_status(self, extra=""):
        self.status_var.set(STEP_LABELS.get(self.step, "") + extra)

    def _update_buttons(self):
        has_undo = (self.undo_stack
                    and self.undo_stack[-1][0] == self.step)
        self.undo_btn.configure(
            state="normal" if has_undo else "disabled")
        self.confirm_btn.configure(
            state="normal" if self.step < 4 else "disabled")
        self.extract_btn.configure(
            state="normal" if self.target_color is not None else "disabled")
        self.save_btn.configure(
            state="normal" if self.extracted else "disabled")


# ═══════════════════════════════════════════════════════════════════════════
# Root application
# ═══════════════════════════════════════════════════════════════════════════
class App(tk.Tk):

    def __init__(self, input_dir="", output_dir=""):
        super().__init__()
        self.title("Plot Digitizer v1.0.0")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.settings = {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "y_axis_type": "linear",
            "smooth": False,
            "colors": dict(DEFAULT_COLORS),
        }

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_start_page()

    def show_start_page(self):
        for w in self.container.winfo_children():
            w.destroy()
        self.title("Plot Digitizer v1.0.0")
        self.geometry("780x620")
        StartPage(self.container, self).pack(fill="both", expand=True)

    def show_settings(self):
        for w in self.container.winfo_children():
            w.destroy()
        self.title("Plot Digitizer — Settings")
        self.geometry("780x620")
        SettingsPage(self.container, self).pack(fill="both", expand=True)

    def show_digitizer(self):
        for w in self.container.winfo_children():
            w.destroy()
        self.geometry("1200x800")
        PlotDigitizer(self.container, self).pack(fill="both", expand=True)

    def _on_close(self):
        self.quit()
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_in = os.path.abspath(os.path.join(script_dir, "..", "pictures"))
    default_out = os.path.abspath(os.path.join(script_dir, "output"))

    input_dir = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1
                 else (default_in if os.path.isdir(default_in) else ""))
    output_dir = (os.path.abspath(sys.argv[2]) if len(sys.argv) > 2
                  else default_out)

    app = App(input_dir=input_dir, output_dir=output_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
