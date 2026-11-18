import tkinter as tk
import ttkbootstrap as ttkbs
from tkinter import scrolledtext
from ttkbootstrap.constants import SUCCESS
from functools import partial
from hbc import distance_sensor_controls
from common_utilities import common_ui_info, constants
from model.ilink_model import set_hardware_status
from controller.ilink_controller import run_command_with_spinner_buttons_info


class DistanceSensorTab:
    def __init__(self, parent):
        self.tab = ttkbs.Frame(parent)
        parent.add(self.tab, text="Distance Sensor")

        # Layout
        self.tab.rowconfigure(0, weight=0)  # graph + current label
        self.tab.rowconfigure(1, weight=1)  # output box
        self.tab.rowconfigure(2, weight=0)  # toggle frame
        self.tab.columnconfigure(0, weight=0)  # button zone
        self.tab.columnconfigure(1, weight=1)  # main area

        # Graph state
        self._samples = []
        self._max_points = 300
        self._pad_l, self._pad_r, self._pad_t, self._pad_b = 40, 10, 10, 25

        self.buttons = []
        self._build_buttons()
        self._build_output_area()

        common_ui_info.register_tab(self)

    def _build_buttons(self):
        """Create the button panel and commands for Distance sensor."""
        button_zone = ttkbs.Frame(self.tab)
        button_zone.grid(row=0, column=0, rowspan=3, sticky="nw", padx=10, pady=10)

        def add_button(text, command, row, bootstyle=SUCCESS):
            btn = ttkbs.Button(
                button_zone,
                text=text,
                width=18,
                bootstyle=bootstyle,
                command=command,
            )
            btn.grid(row=row, column=0, pady=5, sticky="ew")
            self.buttons.append(btn)

        tk.Label(button_zone, text=constants.GAIN).grid(row=0, column=1, padx=0)
        self.gain = ttkbs.Entry(button_zone, width=6)
        self.gain.grid(row=0, column=2, padx=0)
        self.gain.insert(0, "1")

        tk.Label(button_zone, text=constants.OFFSET).grid(row=0, column=3, padx=0)
        self.offset = ttkbs.Entry(button_zone, width=6)
        self.offset.grid(row=0, column=4, padx=0)
        self.offset.insert(0, "0")

        add_button(
            constants.SET_DISTANCE_SENSOR_SETTINGS,
            lambda: run_command_with_spinner_buttons_info(
                partial(
                    distance_sensor_controls.set_distance_sensor_settings,
                    float(self.gain.get() or 1),
                    float(self.offset.get() or 0),
                ),
                self.output_box,
                self.toggle_frame,
                self.tab,
                self.buttons,
                set_hardware_status,
            ),
            0,
        )

        tk.Label(button_zone, text=constants.RUNTIME).grid(row=2, column=1, padx=0)
        self.runtime = ttkbs.Entry(button_zone, width=6)
        self.runtime.grid(row=2, column=2, padx=0)
        self.runtime.insert(0, "5")

        add_button(
            constants.START_DISTANCE_SENSOR_RANGING,
            lambda: self._start_ranging_command(),
            2,
        )

    def _start_ranging_command(self):
        # reset graph before each run
        self._samples = []
        self._draw_axes()
        self.current_distance_var.set("Current Distance: -- mm")

        run_command_with_spinner_buttons_info(
            partial(
                distance_sensor_controls.distance_sensor_start_stop_ranging,
                int(self.runtime.get() or 5),
                5,  # timeout
                self._on_sample_threadsafe,  # live callback
            ),
            self.output_box,
            self.toggle_frame,
            self.tab,
            self.buttons,
            set_hardware_status,
        )

    def _build_output_area(self):
        """Create graph + current-distance label + output text box + toggle frame."""
        top_row = ttkbs.Frame(self.tab)
        top_row.grid(row=0, column=1, sticky="nsew", padx=10, pady=(10, 5))
        top_row.columnconfigure(0, weight=1)

        self.graph_canvas = tk.Canvas(
            top_row,
            width=760,
            height=190,
            bg="white",
            highlightthickness=1,
            highlightbackground="#cccccc",
        )
        self.graph_canvas.grid(row=0, column=0, sticky="ew")

        self.current_distance_var = tk.StringVar(value="Current Distance: -- mm")
        self.current_distance_label = ttkbs.Label(
            top_row,
            textvariable=self.current_distance_var,
            font=("TkDefaultFont", 11, "bold"),
        )
        self.current_distance_label.place(relx=1.0, x=-12, y=8, anchor="ne")

        self._draw_axes()

        self.output_box = scrolledtext.ScrolledText(self.tab, width=75, height=10)
        self.output_box.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        self.output_box.config(state="disabled")

        self.toggle_frame = tk.Frame(self.tab)
        self.toggle_frame.grid(row=2, column=1, sticky="nsew", padx=10, pady=5)

    def _on_sample_threadsafe(self, elapsed_s, distance_mm):
        """Called from worker thread; marshal to Tk main thread."""
        self.tab.after(0, lambda: self._add_sample_and_redraw(elapsed_s, distance_mm))

    def _add_sample_and_redraw(self, elapsed_s, distance_mm):
        self._samples.append((elapsed_s, distance_mm))
        if len(self._samples) > self._max_points:
            self._samples = self._samples[-self._max_points:]

        self.current_distance_var.set(f"Current Distance: {distance_mm:.2f} mm")
        self._redraw_plot()

    def _draw_axes(self):
        c = self.graph_canvas
        c.delete("all")
        w = int(c["width"])
        h = int(c["height"])
        pl, pr, pt, pb = self._pad_l, self._pad_r, self._pad_t, self._pad_b

        c.create_line(pl, h - pb, w - pr, h - pb, fill="#888888")  # x-axis
        c.create_line(pl, pt, pl, h - pb, fill="#888888")          # y-axis

        c.create_text(8, pt, text="mm", anchor="nw", fill="#666666")
        c.create_text(w - 6, h - 6, text="time", anchor="se", fill="#666666")
        c.create_text(pl + 5, h - pb + 2, text="0", anchor="nw", fill="#666666")

    def _redraw_plot(self):
        self._draw_axes()
        if len(self._samples) < 2:
            return

        c = self.graph_canvas
        w = int(c["width"])
        h = int(c["height"])
        pl, pr, pt, pb = self._pad_l, self._pad_r, self._pad_t, self._pad_b
        plot_w = w - pl - pr
        plot_h = h - pt - pb

        ts = [t for t, _ in self._samples]
        ds = [d for _, d in self._samples]

        t_min, t_max = min(ts), max(ts)
        d_min, d_max = min(ds), max(ds)

        if t_max == t_min:
            t_max += 1e-6
        if d_max == d_min:
            d_min -= 1.0
            d_max += 1.0

        pts = []
        for t, d in self._samples:
            x = pl + ((t - t_min) / (t_max - t_min)) * plot_w
            y = pt + (1.0 - ((d - d_min) / (d_max - d_min))) * plot_h
            pts.extend([x, y])

        c.create_line(*pts, fill="#0d6efd", width=2)

        c.create_text(pl + 3, pt + 2, text=f"{d_max:.1f}", anchor="nw", fill="#666666")
        c.create_text(pl + 3, h - pb - 2, text=f"{d_min:.1f}", anchor="sw", fill="#666666")
        c.create_text(w - pr, h - pb + 2, text=f"{t_max - t_min:.1f}s window", anchor="ne", fill="#666666")
