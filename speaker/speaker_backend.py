import platform
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


class SpeakerBackend:
    def __init__(self, resources_dir: Path):
        self.resources_dir = Path(resources_dir)
        self.player_proc: Optional[subprocess.Popen] = None
        self.system = platform.system().lower()  # "windows", "linux", "darwin", ...

    # ---------- Internal helpers ----------
    def _run_cmd(self, cmd: List[str]):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as e:
            class _Result:
                returncode = 127
                stdout = ""
                stderr = str(e)
            return _Result()

    def _cmd_exists(self, cmd: str) -> bool:
        res = self._run_cmd(["where", cmd] if self.system == "windows" else ["which", cmd])
        return res.returncode == 0

    # ---------- Discovery ----------
    def list_output_devices(self) -> List[str]:
        if self.system == "windows":
            return ["default"]

        devices: List[str] = []

        # Linux/Unix path
        res = self._run_cmd(["pactl", "list", "short", "sinks"])
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    devices.append(parts[1])

        if devices:
            return devices

        res = self._run_cmd(["aplay", "-L"])
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                s = line.strip()
                if s and not line.startswith(" "):
                    devices.append(s)

        return devices or ["default"]

    def has_real_sink(self) -> bool:
        devices = self.list_output_devices()
        # If only auto_null exists, no real audio route (Linux case)
        return any(d != "auto_null" for d in devices)

    def list_bundled_wavs(self) -> List[str]:
        if not self.resources_dir.exists():
            return []
        return sorted([p.name for p in self.resources_dir.glob("*.wav")])

    def resolve_bundled_wav(self, name: str) -> Path:
        return self.resources_dir / name

    # ---------- Playback ----------
    def stop_playback(self):
        if self.player_proc and self.player_proc.poll() is None:
            try:
                self.player_proc.terminate()
                self.player_proc.wait(timeout=1)
            except Exception:
                try:
                    self.player_proc.kill()
                except Exception:
                    pass
        self.player_proc = None

    def play_file(self, wav_path: Path, device: str) -> Tuple[bool, str]:
        if not wav_path.exists():
            return False, f"File not found: {wav_path}"

        self.stop_playback()

        # ---------------- Windows ----------------
        if self.system == "windows":
            # Use PowerShell + SoundPlayer (works for .wav without external deps)
            # Device selection is not supported by this method; uses default output device.
            ps_script = (
                "Add-Type -AssemblyName System;"
                f"$p = New-Object System.Media.SoundPlayer('{str(wav_path)}');"
                "$p.PlaySync();"
            )
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]
            try:
                self.player_proc = subprocess.Popen(cmd)
                return True, ""
            except Exception as e:
                return False, f"Failed to start playback on Windows: {e}"

        # ---------------- Linux ----------------
        # Prefer paplay for Pulse/PipeWire sink names
        if self._cmd_exists("paplay"):
            if device and device != "default":
                cmd = ["paplay", "--device", device, str(wav_path)]
            else:
                cmd = ["paplay", str(wav_path)]
            try:
                self.player_proc = subprocess.Popen(cmd)
                return True, ""
            except Exception:
                pass  # try aplay fallback next

        # Fallback to aplay
        if self._cmd_exists("aplay"):
            try:
                self.player_proc = subprocess.Popen(["aplay", "-D", device or "default", str(wav_path)])
                return True, ""
            except Exception as e:
                return False, f"Failed to start playback: {e}"

        return False, "No supported audio player found (tried paplay/aplay)."

    # ---------- Volume ----------
    def set_volume(self, sink: str, pct: int) -> Tuple[bool, str]:
        pct = max(0, min(100, int(pct)))

        if self.system == "windows":
            # Could be implemented via pycaw, but that adds packaging complexity.
            return False, "Volume control via sink is not supported on Windows in this build."

        # Linux path
        if not sink:
            sink = "@DEFAULT_SINK@"

        if not self._cmd_exists("pactl"):
            return False, "pactl not found; cannot control volume."

        if pct == 0:
            mute_res = self._run_cmd(["pactl", "set-sink-mute", sink, "1"])
            if mute_res.returncode != 0:
                return False, (mute_res.stderr or "").strip() or "Failed to mute sink"
            return True, ""
        else:
            vol_res = self._run_cmd(["pactl", "set-sink-volume", sink, f"{pct}%"])
            mute_res = self._run_cmd(["pactl", "set-sink-mute", sink, "0"])
            if vol_res.returncode != 0 or mute_res.returncode != 0:
                err = ((vol_res.stderr or "") + "\n" + (mute_res.stderr or "")).strip()
                return False, err or "Failed to set volume"
            return True, ""
