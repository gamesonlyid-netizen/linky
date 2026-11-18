import sys
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import SUCCESS, WARNING

from common_utilities.log_config import logger
from common_utilities import constants
from controller.ilink_controller import run_command_with_spinner_buttons_info
from source.hbc.hbc_utils import get_hbc_instance

pb2_path = os.path.join(os.path.dirname(__file__), "..", "..", "neo-calibration-server-api", "source", "python")
if pb2_path not in sys.path:
    sys.path.insert(0, pb2_path)
import calibration_server_api_pb2 as calibration_pb2  # noqa: E402

from dmd.dmd_controls import send_dmd_bmp_via_cal_server


class DmdTab:
    def __init__(self, parent):
        self.tab = ttkbs.Frame(parent)
        parent.add(self.tab, text="DMD")
        self.tab.columnconfigure(1, weight=1)

        self.resources_dir = self._resolve_resources_dir()
        self.default_bmp = self.resources_dir / "dotImage_3_5x3-r.bmp"
        self.selected_bmp = self.default_bmp if self.default_bmp.exists() else None

        self.buttons = []
        self._build_ui()

    def _get_app_base_dir(self) -> Path:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[2]

    def _resolve_resources_dir(self) -> Path:
        base = self._get_app_base_dir()
        c1 = base / "resources"
        c2 = base / "source" / "resources"
        if c1.exists():
            return c1
        if c2.exists():
            return c2
        return c1

    def _add_button(self, parent, **kwargs):
        b = ttkbs.Button(parent, **kwargs)
        self.buttons.append(b)
        return b

    def _build_ui(self):
        row = 0

        ttkbs.Label(self.tab, text="BMP file").grid(row=row, column=0, sticky="w", padx=10, pady=8)

        self.bmp_var = tk.StringVar(value=str(self.selected_bmp) if self.selected_bmp else "(none)")
        ttkbs.Label(self.tab, textvariable=self.bmp_var, width=80).grid(row=row, column=1, sticky="w", padx=10, pady=8)

        row += 1
        self._add_button(
            self.tab, text="Browse BMP", bootstyle=WARNING, command=self._browse_bmp
        ).grid(row=row, column=1, sticky="w", padx=10, pady=6)

        row += 1
        self._add_button(
            self.tab, text="Send DMD + Start CW 30s", bootstyle=SUCCESS, command=self._send_dmd_and_start_cw
        ).grid(row=row, column=1, sticky="w", padx=10, pady=10)

        row += 1
        self.output = tk.Text(self.tab, height=8, width=90, state="disabled")
        self.output.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        row += 1
        self.toggle_frame = tk.Frame(self.tab)
        self.toggle_frame.grid(row=row, column=1, sticky="ew", padx=10, pady=5)

    def _browse_bmp(self):
        start_dir = str(self.resources_dir if self.resources_dir.exists() else Path.home())
        path = filedialog.askopenfilename(
            initialdir=start_dir,
            title="Choose BMP file",
            filetypes=[("BMP files", "*.bmp")]
        )
        if path:
            self.selected_bmp = Path(path)
            self.bmp_var.set(str(self.selected_bmp))

    def _append_output(self, text: str):
        self.output.config(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.config(state="disabled")

    def _send_dmd_and_start_cw(self):
        if not self.selected_bmp:
            messagebox.showwarning("No BMP selected", "Choose a BMP file first.")
            return

        def command():
            lines = []
            lines.append(f"BMP: {self.selected_bmp}")

            ok, msg = send_dmd_bmp_via_cal_server(
                bmp_path=self.selected_bmp,
                host="127.0.0.1",
                port=constants.CAL_SERVER_PORT,
                calibration_pb2_module=calibration_pb2,
                socket_timeout=6.0,
            )
            lines.append(f"DMD send: {'SUCCESS' if ok else 'FAILED'} - {msg}")
            if not ok:
                return "\n".join(lines)

            hbc = get_hbc_instance()
            if not hbc:
                lines.append("FAILED: HBC unavailable")
                return "\n".join(lines)

            # irradiance=30000, treatment_time_ms=30000
            hbc.start_cw_treatment(30000, 30000)
            lines.append("CW treatment started: irradiance=30000, duration=30000ms")
            return "\n".join(lines)

        run_command_with_spinner_buttons_info(
            command_fn=command,
            output_box=self.output,
            toggle_frame=self.toggle_frame,
            parent_frame=self.tab,
            buttons=self.buttons,
            set_hardware_status=lambda *_: None,
            on_complete=lambda result: self._append_output(str(result)),
        )
        
# import sys
# import os
# import tkinter as tk
# from pathlib import Path
# from tkinter import filedialog, messagebox
# import ttkbootstrap as ttkbs
# from ttkbootstrap.constants import SUCCESS, WARNING

# from common_utilities.log_config import logger
# from common_utilities import constants
# from controller.ilink_controller import run_command_with_spinner_buttons_info

# # Import generated proto for calibration server
# pb2_path = os.path.join(os.path.dirname(__file__), '..', '..', 'neo-calibration-server-api', 'source', 'python')
# sys.path.insert(0, pb2_path)
# import calibration_server_api_pb2 as calibration_pb2

# from dmd.dmd_controls import send_dmd_bmp_via_cal_server


# class DmdTab:
#     def __init__(self, parent):
#         self.tab = ttkbs.Frame(parent)
#         parent.add(self.tab, text="DMD")

#         self.tab.columnconfigure(1, weight=1)

#         self.resources_dir = self._resolve_resources_dir()
#         self.default_bmp = self.resources_dir / "dotImage_3_5x3-r.bmp"
#         self.selected_bmp = self.default_bmp if self.default_bmp.exists() else None

#         self._build_ui()

#     def _get_app_base_dir(self) -> Path:
#         if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
#             return Path(sys._MEIPASS)
#         return Path(__file__).resolve().parents[2]

#     def _resolve_resources_dir(self) -> Path:
#         base = self._get_app_base_dir()
#         c1 = base / "resources"                # pyinstaller --add-data ...:resources
#         c2 = base / "source" / "resources"     # source run
#         if c1.exists():
#             return c1
#         if c2.exists():
#             return c2
#         return c1

#     def _build_ui(self):
#         row = 0

#         ttkbs.Label(self.tab, text="BMP file").grid(row=row, column=0, sticky="w", padx=10, pady=8)

#         self.bmp_var = tk.StringVar(value=str(self.selected_bmp) if self.selected_bmp else "(none)")
#         self.bmp_label = ttkbs.Label(self.tab, textvariable=self.bmp_var, width=80)
#         self.bmp_label.grid(row=row, column=1, sticky="w", padx=10, pady=8)

#         row += 1
#         ttkbs.Button(
#             self.tab, text="Browse BMP", bootstyle=WARNING, command=self._browse_bmp
#         ).grid(row=row, column=1, sticky="w", padx=10, pady=6)

#         row += 1
#         ttkbs.Button(
#             self.tab, text="Apply DMD Pattern", bootstyle=SUCCESS, command=self._send_dmd
#         ).grid(row=row, column=1, sticky="w", padx=10, pady=10)

#         row += 1
#         self.output = tk.Text(self.tab, height=8, width=90, state="disabled")
#         self.output.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

#     def _browse_bmp(self):
#         start_dir = str(self.resources_dir if self.resources_dir.exists() else Path.home())
#         path = filedialog.askopenfilename(
#             initialdir=start_dir,
#             title="Choose BMP file",
#             filetypes=[("BMP files", "*.bmp")]
#         )
#         if path:
#             self.selected_bmp = Path(path)
#             self.bmp_var.set(str(self.selected_bmp))

#     def _append_output(self, text: str):
#         self.output.config(state="normal")
#         self.output.insert("end", text + "\n")
#         self.output.see("end")
#         self.output.config(state="disabled")

#     def _send_dmd(self):
#         if not self.selected_bmp:
#             messagebox.showwarning("No BMP selected", "Choose a BMP file first.")
#             return

#         def command():
#             logger.info("Sending DMD BMP: %s", self.selected_bmp)
#             ok, msg = send_dmd_bmp_via_cal_server(
#                 bmp_path=self.selected_bmp,
#                 host="127.0.0.1",
#                 port=constants.CAL_SERVER_PORT,  # from your constants
#                 calibration_pb2_module=calibration_pb2,
#             )
#             return f"{'SUCCESS' if ok else 'FAILED'}: {msg}"

#         run_command_with_spinner_buttons_info(
#             command_fn=command,
#             output_box=self.output,
#             toggle_frame=tk.Frame(self.tab),   # unused in this tab
#             parent_frame=self.tab,
#             buttons=[],
#             set_hardware_status=lambda *_: None,
#             on_complete=lambda result: self._append_output(str(result)),
#         )