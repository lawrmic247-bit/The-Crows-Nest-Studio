"""Reliable local audio previews: play in-app, stop, and report device errors.

FFplay is preferred because it handles WAV/MP3/M4A and has an explicit stop
control. Windows' built-in WAV player is the fallback if FFplay is unavailable.
No cloud services and no Python playback package are required.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


class PlaybackError(RuntimeError):
    pass


def find_ffplay() -> str | None:
    candidate = shutil.which("ffplay") or shutil.which("ffplay.exe")
    if candidate:
        return candidate
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffplay.exe" if sys.platform == "win32" else "ffplay")
        if sibling.is_file():
            return str(sibling)
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        packages = local / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            # Only scan the packaged FFmpeg distributions, not the whole disk.
            for folder in packages.glob("*FFmpeg*"):
                for candidate_path in folder.glob("**/bin/ffplay.exe"):
                    if candidate_path.is_file():
                        return str(candidate_path)
    return None


class AudioPlayer:
    """One player per window. Playback never opens an external media app."""

    def __init__(self):
        self.process = None
        self.backend = None
        self.current_file = None

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
            finally:
                if process.stderr:
                    process.stderr.close()
        if self.backend == "Windows WAV":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except (ImportError, RuntimeError):
                pass
        self.backend = None
        self.current_file = None

    def play(self, path: str | Path) -> str:
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise PlaybackError(f"Audio file not found: {path}")
        if path.stat().st_size < 44:
            raise PlaybackError(f"The recording is empty or incomplete: {path.name}")

        self.stop()
        ffplay = find_ffplay()
        detail = ""
        if ffplay:
            command = [ffplay, "-nodisp", "-autoexit", "-hide_banner",
                       "-loglevel", "error", "-nostats", str(path)]
            options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                       "stderr": subprocess.PIPE}
            if sys.platform == "win32":
                options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                process = subprocess.Popen(command, **options)
                time.sleep(0.12)
                rc = process.poll()
                if rc is None or rc == 0:
                    self.process = process
                    self.backend = "FFplay"
                    self.current_file = path
                    return self.backend
                detail = (process.stderr.read(4096) or b"").decode("utf-8", "replace").strip()
                process.stderr.close()
            except OSError as exc:
                detail = str(exc)

        if sys.platform == "win32" and path.suffix.lower() == ".wav":
            try:
                import winsound
                winsound.PlaySound(str(path),
                                   winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                self.backend = "Windows WAV"
                self.current_file = path
                return self.backend
            except (OSError, RuntimeError) as exc:
                detail = str(exc)

        raise PlaybackError(
            "Could not play this audio through the Windows output device. "
            "Check the default speaker, volume mixer, and that FFplay is installed "
            "alongside FFmpeg." + (f"\n\nDetails: {detail}" if detail else "")
        )
