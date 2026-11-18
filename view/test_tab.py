import tkinter as tk
import ttkbootstrap as ttkbs
import threading
import os, sys
from PIL import ImageTk
from common_utilities.log_config import logger
from ttkbootstrap.constants import SUCCESS, DANGER, NORMAL, DISABLED
from source.common_utilities import constants

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from calibration.camera_streaming import (
    UVLaunchStreamConnection,   # new, see section 2
    raw_to_image,
    resize_image,
)


class TestTab:
    def __init__(self, parent):
        self.tab = ttkbs.Frame(parent)
        parent.add(self.tab, text="Test")

        self.tab.rowconfigure(0, weight=0)
        self.tab.rowconfigure(1, weight=1)
        self.tab.columnconfigure(0, weight=1)

        # Buttons
        self.button_frame = ttkbs.Frame(self.tab)
        self.button_frame.grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.start_btn = ttkbs.Button(
            self.button_frame, text="Start UV Launch", width=15,
            bootstyle=SUCCESS, command=self.start_stream)
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ttkbs.Button(
            self.button_frame, text="Stop UV Launch", width=15,
            bootstyle=DANGER, command=self.stop_stream)
        self.stop_btn.pack(side="left", padx=5)

        self.status_label = ttkbs.Label(self.button_frame, text="Ready", font=("Arial", 10))
        self.status_label.pack(side="left", padx=20)

        # Video area
        container = ttkbs.Frame(self.tab)
        container.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        ttkbs.Label(container, text="UV Launch", font=("Arial", 12, "bold")).grid(
            row=0, column=0, sticky="n", pady=5)

        frame = tk.Frame(container, border=2, relief=tk.RAISED, bg="white")
        frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.image_label = tk.Label(frame, background="black")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        self.current_photo = None  # keep reference

        self.conn = UVLaunchStreamConnection(host=constants.UVC_IP, port=constants.CAL_SERVER_PORT)

    # ---- helpers (always call from the Tk thread) ----
    def update_status(self, message):
        self.status_label.config(text=message)

    def _ui(self, fn):
        """Schedule fn on the Tk main thread."""
        self.image_label.after(0, fn)

    # ---- start ----
    def start_stream(self):
        if self.conn.streaming:
            self.update_status("UV Launch stream already running!")
            return
        self.start_btn.config(state=DISABLED)
        self.update_status("Connecting UV Launch...")
        threading.Thread(target=self._stream_thread, daemon=True).start()

    def _stream_thread(self):
        try:
            if not self.conn.connected and not self.conn.connect():
                self._ui(lambda: self.update_status("Failed to connect UV Launch"))
                return

            if not self.conn.start_streaming(self._on_frame):
                self._ui(lambda: self.update_status("Failed to start UV Launch stream"))
                return

            self._ui(lambda: self.update_status("UV Launch stream started!"))
        except Exception as e:
            logger.error(f"UV Launch stream error: {e}")
            self._ui(lambda: self.update_status(f"Error: {e}"))
        finally:
            self._ui(lambda: self.start_btn.config(state=NORMAL))

    # ---- frames (called from the stream thread) ----
    def _on_frame(self, frame_data):
        try:
            cam = frame_data['uv_launch']
            img = raw_to_image(cam['image'], cam['width'], cam['height'])
            n = frame_data.get('frame_number', '?')
            self._ui(lambda: self._display_frame(img))
            self._ui(lambda: self.update_status(f"UV Launch Frame {n}: {cam['width']}x{cam['height']}"))
        except Exception as e:
            logger.error(f"Error processing UV Launch frame: {e}")

    def _display_frame(self, pil_img):
        if pil_img is None:
            return
        try:
            pil_img = resize_image(pil_img, 600, 600)
            photo = ImageTk.PhotoImage(pil_img)
            self.image_label.config(image=photo)
            self.current_photo = photo
        except Exception as e:
            logger.error(f"Error displaying frame: {e}")

    # ---- stop ----
    def stop_stream(self):
        if not self.conn.streaming:
            self.update_status("UV Launch stream not running!")
            return
        self.update_status("Stopping UV Launch stream...")
        try:
            self.conn.stop_streaming()
            if self.conn.stream_thread and self.conn.stream_thread.is_alive():
                self.conn.stream_thread.join(timeout=2)
            self.conn.disconnect()
            self.update_status("UV Launch stream stopped!")
        except Exception as e:
            logger.error(f"Error stopping UV Launch stream: {e}")
            self.update_status(f"Error: {e}")