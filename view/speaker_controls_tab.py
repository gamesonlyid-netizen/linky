import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttkbs
from ttkbootstrap.constants import SUCCESS, WARNING, DANGER

from common_utilities.log_config import logger
from speaker.speaker_backend import SpeakerBackend


class SpeakerControlsTab:
    def __init__(self, parent):
        self.tab = ttkbs.Frame(parent)
        parent.add(self.tab, text="Speaker")

        # Resolve resources for BOTH:
        # - normal source run
        # - PyInstaller onefile/onedir
        resources_dir = self._resolve_resources_dir()
        logger.info("SpeakerControlsTab resources_dir=%s exists=%s", resources_dir, resources_dir.exists())

        self.backend = SpeakerBackend(resources_dir=resources_dir)

        self.selected_external_file = None
        self.tab.columnconfigure(1, weight=1)

        self._build_ui()
        self._load_devices()
        self._load_resource_wavs()
        self._update_audio_health_banner()

    def _get_app_base_dir(self) -> Path:
        # PyInstaller onefile/onedir base extraction dir
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        # Running from source
        return Path(__file__).resolve().parents[2]

    def _resolve_resources_dir(self) -> Path:
        base = self._get_app_base_dir()

        # For your current packaging:
        # --add-data=source/resources:resources
        # => resources live at <base>/resources
        candidate_bundle = base / "resources"

        # For source/dev runs:
        candidate_source = base / "source" / "resources"

        if candidate_bundle.exists():
            return candidate_bundle
        if candidate_source.exists():
            return candidate_source

        # fallback (still return bundle-style target for clearer logging/debugging)
        return candidate_bundle

    def _build_ui(self):
        row = 0

        self.health_var = tk.StringVar(value="")
        self.health_label = ttkbs.Label(self.tab, textvariable=self.health_var, bootstyle="warning")
        self.health_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))

        row += 1
        ttkbs.Label(self.tab, text="Output Device").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        self.device_var = tk.StringVar(value="default")
        self.device_combo = ttkbs.Combobox(self.tab, textvariable=self.device_var, state="readonly", width=55)
        self.device_combo.grid(row=row, column=1, sticky="ew", padx=10, pady=6)

        row += 1
        ttkbs.Button(self.tab, text="Refresh Devices", command=self._load_devices).grid(
            row=row, column=1, sticky="w", padx=10, pady=4
        )

        row += 1
        ttkbs.Label(self.tab, text="Bundled WAV").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        self.wav_var = tk.StringVar()
        self.wav_combo = ttkbs.Combobox(self.tab, textvariable=self.wav_var, state="readonly", width=55)
        self.wav_combo.grid(row=row, column=1, sticky="ew", padx=10, pady=6)

        row += 1
        ttkbs.Button(
            self.tab,
            text="Browse WAV from Desktop",
            bootstyle=WARNING,
            command=self._browse_wav,
        ).grid(row=row, column=1, sticky="w", padx=10, pady=6)

        row += 1
        self.external_label_var = tk.StringVar(value="External file: (none)")
        ttkbs.Label(self.tab, textvariable=self.external_label_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2
        )

        row += 1
        controls = ttkbs.Frame(self.tab)
        controls.grid(row=row, column=1, sticky="w", padx=10, pady=10)

        self.btn_play_bundled = ttkbs.Button(
            controls, text="Play Bundled", bootstyle=SUCCESS, command=self._play_bundled
        )
        self.btn_play_bundled.grid(row=0, column=0, padx=4)

        self.btn_play_external = ttkbs.Button(
            controls, text="Play External", bootstyle=SUCCESS, command=self._play_external
        )
        self.btn_play_external.grid(row=0, column=1, padx=4)

        self.btn_stop = ttkbs.Button(
            controls, text="Stop", bootstyle=DANGER, command=self.backend.stop_playback
        )
        self.btn_stop.grid(row=0, column=2, padx=4)

        row += 1
        ttkbs.Label(self.tab, text="Volume").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        self.vol_frame = ttkbs.Frame(self.tab)
        self.vol_frame.grid(row=row, column=1, sticky="w", padx=10, pady=6)

        self.volume_buttons = []
        for i, (label, val) in enumerate(
            [("Mute", 0), ("20%", 20), ("40%", 40), ("60%", 60), ("80%", 80), ("100%", 100)]
        ):
            b = ttkbs.Button(self.vol_frame, text=label, command=lambda v=val: self._set_volume(v))
            b.grid(row=0, column=i, padx=3)
            self.volume_buttons.append(b)

    def _load_devices(self):
        devices = self.backend.list_output_devices()
        self.device_combo["values"] = devices
        self.device_var.set("default" if "default" in devices else devices[0])
        self._update_audio_health_banner()

    def _load_resource_wavs(self):
        wavs = self.backend.list_bundled_wavs()
        logger.info("SpeakerControlsTab wav files found=%s", wavs)
        self.wav_combo["values"] = wavs
        self.wav_var.set(wavs[0] if wavs else "")

    def _browse_wav(self):
        desktop = Path.home() / "Desktop"
        path = filedialog.askopenfilename(
            initialdir=str(desktop if desktop.exists() else Path.home()),
            title="Choose WAV file",
            filetypes=[("WAV files", "*.wav")],
        )
        if path:
            self.selected_external_file = Path(path)
            self.external_label_var.set(f"External file: {self.selected_external_file}")

    def _play_bundled(self):
        name = self.wav_var.get().strip()
        if not name:
            messagebox.showwarning("No bundled WAV", "No WAV found in packaged resources.")
            return
        wav_path = self.backend.resolve_bundled_wav(name)
        ok, err = self.backend.play_file(wav_path, self.device_var.get().strip())
        if not ok:
            messagebox.showerror("Playback Error", err)

    def _play_external(self):
        if not self.selected_external_file:
            messagebox.showwarning("No external WAV", "Choose a WAV from Desktop first.")
            return
        ok, err = self.backend.play_file(self.selected_external_file, self.device_var.get().strip())
        if not ok:
            messagebox.showerror("Playback Error", err)

    def _set_volume(self, pct: int):
        sink = self.device_var.get().strip() or "@DEFAULT_SINK@"
        ok, err = self.backend.set_volume(sink, pct)
        if not ok:
            messagebox.showerror("Volume Error", err)

    def _update_audio_health_banner(self):
        devices = list(self.device_combo["values"]) if self.device_combo["values"] else []
        only_auto_null = (len(devices) == 1 and devices[0] == "auto_null")

        if only_auto_null:
            self.health_var.set("⚠ No physical audio sink detected (only auto_null). Playback will be silent.")
            self._set_controls_enabled(False)
        else:
            self.health_var.set("")
            self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_play_bundled.configure(state=state)
        self.btn_play_external.configure(state=state)
        self.btn_stop.configure(state=state)
        for b in self.volume_buttons:
            b.configure(state=state)