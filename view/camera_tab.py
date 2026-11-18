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
    StereoStreamConnection, 
    WideStreamConnection,
    raw_to_image,
    resize_image
)


class CameraTab:
    def __init__(self, parent):
        self.tab = ttkbs.Frame(parent)
        parent.add(self.tab, text="Camera")

        # Layout configuration
        self.tab.rowconfigure(0, weight=0)
        self.tab.rowconfigure(1, weight=1)
        self.tab.columnconfigure(0, weight=1)

        # Button frame
        self.button_frame = ttkbs.Frame(self.tab)
        self.button_frame.grid(row=0, column=0, pady=10, sticky="w", padx=10)

        self.start_stereo_btn = ttkbs.Button(
            self.button_frame,
            text=constants.CAMERA_START_STEREO,
            width=15,
            bootstyle=SUCCESS,
            command=self.start_stereo_stream
        )
        self.start_stereo_btn.pack(side="left", padx=5)

        self.stop_stereo_btn = ttkbs.Button(
            self.button_frame,
            text=constants.CAMERA_STOP_STEREO,
            width=15,
            bootstyle=DANGER,
            command=self.stop_stereo_stream
        )
        self.stop_stereo_btn.pack(side="left", padx=5)

        self.start_wide_btn = ttkbs.Button(
            self.button_frame,
            text=constants.CAMERA_START_WIDE,
            width=15,
            bootstyle=SUCCESS,
            command=self.start_wide_stream
        )
        self.start_wide_btn.pack(side="left", padx=5)

        self.stop_wide_btn = ttkbs.Button(
            self.button_frame,
            text=constants.CAMERA_STOP_WIDE,
            width=15,
            bootstyle=DANGER,
            command=self.stop_wide_stream
        )
        self.stop_wide_btn.pack(side="left", padx=5)

        # Status label
        self.status_label = ttkbs.Label(self.button_frame, text="Ready", font=("Arial", 10))
        self.status_label.pack(side="left", padx=20)

        # Video frame container
        video_container = ttkbs.Frame(self.tab)
        video_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        video_container.rowconfigure(0, weight=0)
        video_container.rowconfigure(1, weight=1)
        video_container.columnconfigure(0, weight=1)
        video_container.columnconfigure(1, weight=1)
        video_container.columnconfigure(2, weight=1)

        # Left camera
        left_label = ttkbs.Label(video_container, text=constants.CAMERA_STRING_LEFT, font=("Arial", 12, "bold"))
        left_label.grid(row=0, column=0, sticky="n", pady=5)

        left_frame = tk.Frame(video_container, border=2, relief=tk.RAISED, bg="white")
        left_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.left_image_label = tk.Label(left_frame, background="black")
        self.left_image_label.pack(fill=tk.BOTH, expand=True)

        # Right camera
        right_label = ttkbs.Label(video_container, text=constants.CAMERA_STRING_RIGHT, font=("Arial", 12, "bold"))
        right_label.grid(row=0, column=1, sticky="n", pady=5)

        right_frame = tk.Frame(video_container, border=2, relief=tk.RAISED, bg="white")
        right_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        self.right_image_label = tk.Label(right_frame, background="black")
        self.right_image_label.pack(fill=tk.BOTH, expand=True)

        # Wide camera
        wide_label = ttkbs.Label(video_container, text=constants.CAMERA_STRING_WIDE, font=("Arial", 12, "bold"))
        wide_label.grid(row=0, column=2, sticky="n", pady=5)

        wide_frame = tk.Frame(video_container, border=2, relief=tk.RAISED, bg="white")
        wide_frame.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)

        self.wide_image_label = tk.Label(wide_frame, background="black")
        self.wide_image_label.pack(fill=tk.BOTH, expand=True)

        # Cache for PhotoImage references
        self.current_photo_left = None
        self.current_photo_right = None
        self.current_photo_wide = None

        # Streaming connections
        self.stereo_conn = StereoStreamConnection(host=constants.UVC_IP, port=constants.CAL_SERVER_PORT)
        self.wide_conn = WideStreamConnection(host=constants.UVC_IP, port=constants.CAL_SERVER_PORT)

    def update_status(self, message):
        self.status_label.config(text=message)
        self.tab.update()

    def start_stereo_stream(self):
        if self.stereo_conn.streaming:
            self.update_status("Stereo stream already running!")
            return

        self.start_stereo_btn.config(state=DISABLED)
        self.update_status("Connecting stereo...")

        thread = threading.Thread(target=self._stereo_stream_thread, daemon=True)
        thread.start()

    def _stereo_stream_thread(self):
        try:
            if not self.stereo_conn.connected:
                if not self.stereo_conn.connect():
                    self.left_image_label.after(0, lambda: self.update_status("Failed to connect stereo"))
                    self.left_image_label.after(0, lambda: self.start_stereo_btn.config(state=NORMAL))
                    return

            self.update_status("Starting stereo stream...")

            if not self.stereo_conn.start_streaming(self._on_stereo_frame):
                self.left_image_label.after(0, lambda: self.update_status("Failed to start stereo stream"))
                self.left_image_label.after(0, lambda: self.start_stereo_btn.config(state=NORMAL))
                return

            self.left_image_label.after(0, lambda: self.update_status(" Stereo stream started!"))

        except Exception as e:
            logger.error(f"Stereo stream error: {e}")
            self.left_image_label.after(0, lambda: self.update_status(f"Error: {e}"))
        finally:
            self.left_image_label.after(0, lambda: self.start_stereo_btn.config(state=NORMAL))

    def _on_stereo_frame(self, frame_data):
        try:
            # Display left
            left_img = raw_to_image(frame_data['left']['image'], frame_data['left']['width'], frame_data['left']['height'])
            self.left_image_label.after(0, lambda img=left_img: self._display_frame(img, 'left'))

            # Display right
            right_img = raw_to_image(frame_data['right']['image'], frame_data['right']['width'], frame_data['right']['height'])
            self.right_image_label.after(0, lambda img=right_img: self._display_frame(img, 'right'))

            # Update status
            self.left_image_label.after(0, lambda: self.update_status(
                f"Stereo Frame {frame_data['frame_number']}: {frame_data['left']['width']}x{frame_data['left']['height']}"))

        except Exception as e:
            logger.error(f"Error processing stereo frame: {e}")

    def start_wide_stream(self):
        if self.wide_conn.streaming:
            self.update_status("Wide stream already running!")
            return

        self.start_wide_btn.config(state=DISABLED)
        self.update_status("Connecting wide...")

        thread = threading.Thread(target=self._wide_stream_thread, daemon=True)
        thread.start()

    def _wide_stream_thread(self):
        try:
            if not self.wide_conn.connected:
                if not self.wide_conn.connect():
                    self.wide_image_label.after(0, lambda: self.update_status("Failed to connect wide"))
                    self.wide_image_label.after(0, lambda: self.start_wide_btn.config(state=NORMAL))
                    return

            self.update_status("Starting wide stream...")

            if not self.wide_conn.start_streaming(self._on_wide_frame):
                self.wide_image_label.after(0, lambda: self.update_status("Failed to start wide stream"))
                self.wide_image_label.after(0, lambda: self.start_wide_btn.config(state=NORMAL))
                return

            self.wide_image_label.after(0, lambda: self.update_status(" Wide stream started!"))

        except Exception as e:
            logger.error(f"Wide stream error: {e}")
            self.wide_image_label.after(0, lambda: self.update_status(f"Error: {e}"))
        finally:
            self.wide_image_label.after(0, lambda: self.start_wide_btn.config(state=NORMAL))

    def _on_wide_frame(self, frame_data):
        try:
            # Display wide
            wide_img = raw_to_image(frame_data['wide']['image'], frame_data['wide']['width'], frame_data['wide']['height'])
            self.wide_image_label.after(0, lambda img=wide_img: self._display_frame(img, 'wide'))

            # Update status
            self.wide_image_label.after(0, lambda: self.update_status(
                f"Wide Frame {frame_data['frame_number']}: {frame_data['wide']['width']}x{frame_data['wide']['height']}"))

        except Exception as e:
            logger.error(f"Error processing wide frame: {e}")

    def _display_frame(self, pil_img, side):
        if pil_img is None:
            return

        try:
            if side == 'left':
                lbl = self.left_image_label
            elif side == 'right':
                lbl = self.right_image_label
            else:  # wide
                lbl = self.wide_image_label

            # Fixed width to maintain aspect ratio and image rezising.
            lbl_w = 600
            lbl_h = 600

            # Resize image
            pil_img = resize_image(pil_img, lbl_w, lbl_h)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(pil_img)
            lbl.config(image=photo)

            # Keep reference to prevent garbage collection
            if side == 'left':
                self.current_photo_left = photo
            elif side == 'right':
                self.current_photo_right = photo
            else:
                self.current_photo_wide = photo

        except Exception as e:
            logger.error(f"Error displaying frame: {e}")

    def stop_stereo_stream(self):
        if not self.stereo_conn.streaming:
            self.update_status("Stereo stream not running!")
            return

        self.update_status("Stopping stereo stream...")

        try:
            # Stop streaming first
            self.stereo_conn.stop_streaming()
            
            # Wait for thread to finish
            if self.stereo_conn.stream_thread and self.stereo_conn.stream_thread.is_alive():
                self.stereo_conn.stream_thread.join(timeout=2)
            
            # Then disconnect
            self.stereo_conn.disconnect()
            self.update_status("Stereo stream stopped!")

        except Exception as e:
            logger.error(f"Error stopping stereo stream: {e}")
            self.update_status(f"Error: {e}")

    def stop_wide_stream(self):
        if not self.wide_conn.streaming:
            self.update_status("Wide stream not running!")
            return

        self.update_status("Stopping wide stream...")

        try:
            # Stop streaming first
            self.wide_conn.stop_streaming()
            
            # Wait for thread to finish
            if self.wide_conn.stream_thread and self.wide_conn.stream_thread.is_alive():
                self.wide_conn.stream_thread.join(timeout=2)
            
            # Then disconnect
            self.wide_conn.disconnect()
            self.update_status("Wide stream stopped!")

        except Exception as e:
            logger.error(f"Error stopping wide stream: {e}")
            self.update_status(f"Error: {e}")