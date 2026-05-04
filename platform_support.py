"""Cross-platform read-only helpers for the Pulse Suite.

The helpers in this module intentionally do not change host state. They only
collect lightweight local orientation data and normalize platform differences
between Linux, macOS, and Windows.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str
    command: tuple[str, ...]


def os_family() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system or "unknown"


def platform_label() -> str:
    return f"{platform.system() or 'Unknown'} {platform.release() or ''} / {platform.machine() or 'unknown'}".strip()


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: list[str], timeout: float = 2.0) -> CommandResult:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=float(timeout), check=False)
        return CommandResult(result.returncode, result.stdout.strip(), result.stderr.strip(), tuple(command))
    except FileNotFoundError:
        return CommandResult(127, "", "command not found", tuple(command))
    except Exception as exc:
        return CommandResult(1, "", str(exc), tuple(command))


def run_powershell(script: str, timeout: float = 3.0) -> CommandResult:
    candidates = ["powershell", "pwsh"]
    for binary in candidates:
        if command_exists(binary):
            return run_command([binary, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)
    return CommandResult(127, "", "PowerShell not found", ("powershell",))


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except Exception:
        return None


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def bytes_to_gib(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) / (1024 ** 3):.1f} GiB"


def percent(used: int | float | None, total: int | float | None) -> float | None:
    if used is None or total is None or float(total) <= 0:
        return None
    return max(0.0, min(100.0, float(used) / float(total) * 100.0))


def home_ssh_dir() -> Path:
    return Path.home() / ".ssh"


def safe_stat_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode & 0o777
    except Exception:
        return None


def list_windows_drives() -> list[str]:
    drives: list[str] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append(root)
    return drives
