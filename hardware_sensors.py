"""Generic read-only hardware sensor collection for Hardware Pulse.

The collector is intentionally best-effort and local-only.
It does not require sudo, does not write host state, and does not run heavy
scans. Missing sensors are treated as unavailable, not as failures.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HardwareSensor:
    """Normalized sensor row for the Hardware Pulse sensor table."""

    name: str
    category: str
    value: str
    state: str
    note: str
    source: str


DEFAULT_SENSOR_CONFIG = {
    "hardware_enable_sensors": True,
    "hardware_sensor_max_rows": 32,
    "hardware_temperature_warn_celsius": 75.0,
    "hardware_temperature_critical_celsius": 90.0,
    "hardware_fan_min_warn_rpm": 400.0,
    "hardware_fan_min_critical_rpm": 100.0,
    "hardware_fan_zero_is_critical": False,
    "hardware_enable_gpu_tools": False,
    "hardware_sensor_command_timeout_seconds": 1.5,
    "hardware_vram_warn_percent": 80.0,
    "hardware_vram_critical_percent": 95.0,
}

STATE_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}
CATEGORY_SORT = {
    "temperature": 0,
    "gpu_temperature": 1,
    "fan": 2,
    "gpu_usage": 3,
    "vram": 4,
}


def sensor_config(config: dict | None) -> dict:
    """Merge caller config with sensor defaults."""

    merged = dict(DEFAULT_SENSOR_CONFIG)
    if config:
        for key, value in config.items():
            if key in merged:
                merged[key] = value
    return merged


def collect_hardware_sensors(config: dict | None = None) -> list[HardwareSensor]:
    """Collect normalized sensor rows from cheap local sources.

    Default sources:
    - Linux hwmon sysfs: /sys/class/hwmon
    - Linux thermal sysfs: /sys/class/thermal

    Optional sources:
    - nvidia-smi, only when explicitly enabled in config
    """

    cfg = sensor_config(config)
    if not bool(cfg.get("hardware_enable_sensors", True)):
        return []

    sensors: list[HardwareSensor] = []
    sensors.extend(_collect_hwmon_sensors(cfg))
    sensors.extend(_collect_thermal_zone_sensors(cfg, existing=sensors))

    if bool(cfg.get("hardware_enable_gpu_tools", False)):
        sensors.extend(_collect_nvidia_smi_sensors(cfg))

    return _dedupe_sort_and_limit(sensors, int(cfg.get("hardware_sensor_max_rows", 32)))


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return None


def _read_float(path: Path) -> float | None:
    raw = _read_text(path)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _clean_label(raw: str | None, fallback: str) -> str:
    text = (raw or "").strip()
    if not text:
        text = fallback
    return " ".join(text.replace("_", " ").split())


def _temperature_state(celsius: float | None, cfg: dict) -> str:
    if celsius is None:
        return "unknown"
    if celsius >= float(cfg["hardware_temperature_critical_celsius"]):
        return "critical"
    if celsius >= float(cfg["hardware_temperature_warn_celsius"]):
        return "warn"
    return "ok"


def _fan_state(rpm: float | None, cfg: dict) -> str:
    if rpm is None:
        return "unknown"
    if rpm == 0 and not bool(cfg.get("hardware_fan_zero_is_critical", False)):
        return "warn"
    if rpm <= float(cfg["hardware_fan_min_critical_rpm"]):
        return "critical"
    if rpm <= float(cfg["hardware_fan_min_warn_rpm"]):
        return "warn"
    return "ok"


def _fan_note(rpm: float | None) -> str:
    if rpm == 0:
        return "Local hwmon fan sensor. 0 RPM can be normal on fan-stop systems."
    return "Local hwmon fan sensor. Low RPM can be normal on some fan-stop systems."


def _percent_state(percent: float | None, warn: float, critical: float) -> str:
    if percent is None:
        return "unknown"
    if percent >= critical:
        return "critical"
    if percent >= warn:
        return "warn"
    return "ok"


def _collect_hwmon_sensors(cfg: dict) -> list[HardwareSensor]:
    root = Path("/sys/class/hwmon")
    if not root.exists():
        return []

    sensors: list[HardwareSensor] = []
    for hwmon in sorted(root.glob("hwmon*")):
        source_name = _clean_label(_read_text(hwmon / "name"), hwmon.name)
        sensors.extend(_collect_hwmon_temperatures(hwmon, source_name, cfg))
        sensors.extend(_collect_hwmon_fans(hwmon, source_name, cfg))

    return sensors


def _collect_hwmon_temperatures(hwmon: Path, source_name: str, cfg: dict) -> list[HardwareSensor]:
    sensors: list[HardwareSensor] = []
    for input_path in sorted(hwmon.glob("temp*_input")):
        prefix = input_path.name.removesuffix("_input")
        raw_value = _read_float(input_path)
        if raw_value is None:
            continue
        celsius = raw_value / 1000.0
        if celsius < -50 or celsius > 180:
            continue
        label = _clean_label(_read_text(hwmon / f"{prefix}_label"), prefix)
        state = _temperature_state(celsius, cfg)
        sensors.append(
            HardwareSensor(
                name=f"{source_name} {label}",
                category="temperature",
                value=f"{celsius:.1f} °C",
                state=state,
                note="Local hwmon temperature sensor.",
                source=str(input_path),
            )
        )
    return sensors


def _collect_hwmon_fans(hwmon: Path, source_name: str, cfg: dict) -> list[HardwareSensor]:
    sensors: list[HardwareSensor] = []
    for input_path in sorted(hwmon.glob("fan*_input")):
        prefix = input_path.name.removesuffix("_input")
        rpm = _read_float(input_path)
        if rpm is None or rpm < 0:
            continue
        label = _clean_label(_read_text(hwmon / f"{prefix}_label"), prefix)
        state = _fan_state(rpm, cfg)
        sensors.append(
            HardwareSensor(
                name=f"{source_name} {label}",
                category="fan",
                value=f"{rpm:.0f} RPM",
                state=state,
                note=_fan_note(rpm),
                source=str(input_path),
            )
        )
    return sensors


def _collect_thermal_zone_sensors(cfg: dict, existing: list[HardwareSensor]) -> list[HardwareSensor]:
    root = Path("/sys/class/thermal")
    if not root.exists():
        return []

    existing_names = {sensor.name.lower() for sensor in existing}
    sensors: list[HardwareSensor] = []
    for zone in sorted(root.glob("thermal_zone*")):
        temp_path = zone / "temp"
        raw_value = _read_float(temp_path)
        if raw_value is None:
            continue
        celsius = raw_value / 1000.0
        if celsius < -50 or celsius > 180:
            continue
        zone_type = _clean_label(_read_text(zone / "type"), zone.name)
        name = f"thermal {zone_type}"
        if name.lower() in existing_names:
            continue
        state = _temperature_state(celsius, cfg)
        sensors.append(
            HardwareSensor(
                name=name,
                category="temperature",
                value=f"{celsius:.1f} °C",
                state=state,
                note="Local thermal zone temperature sensor.",
                source=str(temp_path),
            )
        )
    return sensors


def _collect_nvidia_smi_sensors(cfg: dict) -> list[HardwareSensor]:
    if shutil.which("nvidia-smi") is None:
        return []

    query = "temperature.gpu,utilization.gpu,memory.used,memory.total"
    command = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    timeout = float(cfg.get("hardware_sensor_command_timeout_seconds", 1.5))

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    sensors: list[HardwareSensor] = []
    for index, line in enumerate(result.stdout.splitlines(), start=1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        temp = _parse_float(parts[0])
        gpu_util = _parse_float(parts[1])
        mem_used = _parse_float(parts[2])
        mem_total = _parse_float(parts[3])

        if temp is not None:
            sensors.append(
                HardwareSensor(
                    name=f"NVIDIA GPU {index} temperature",
                    category="gpu_temperature",
                    value=f"{temp:.1f} °C",
                    state=_temperature_state(temp, cfg),
                    note="Optional nvidia-smi GPU temperature sensor.",
                    source="nvidia-smi",
                )
            )
        if gpu_util is not None:
            sensors.append(
                HardwareSensor(
                    name=f"NVIDIA GPU {index} utilization",
                    category="gpu_usage",
                    value=f"{gpu_util:.1f}%",
                    state=_percent_state(gpu_util, 80.0, 95.0),
                    note="Optional nvidia-smi GPU utilization sensor.",
                    source="nvidia-smi",
                )
            )
        if mem_used is not None and mem_total and mem_total > 0:
            vram_percent = mem_used / mem_total * 100.0
            sensors.append(
                HardwareSensor(
                    name=f"NVIDIA GPU {index} VRAM",
                    category="vram",
                    value=f"{vram_percent:.1f}% / {mem_used:.0f} MiB of {mem_total:.0f} MiB",
                    state=_percent_state(
                        vram_percent,
                        float(cfg["hardware_vram_warn_percent"]),
                        float(cfg["hardware_vram_critical_percent"]),
                    ),
                    note="Optional nvidia-smi VRAM usage sensor.",
                    source="nvidia-smi",
                )
            )

    return sensors


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _sensor_sort_key(sensor: HardwareSensor) -> tuple[int, int, str]:
    return (
        STATE_SORT.get(sensor.state, STATE_SORT["unknown"]),
        CATEGORY_SORT.get(sensor.category, 99),
        sensor.name.lower(),
    )


def _dedupe_sort_and_limit(sensors: list[HardwareSensor], limit: int) -> list[HardwareSensor]:
    seen: set[tuple[str, str, str]] = set()
    result: list[HardwareSensor] = []
    for sensor in sorted(sensors, key=_sensor_sort_key):
        key = (sensor.name.lower(), sensor.category, sensor.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(sensor)
        if len(result) >= max(1, limit):
            break
    return result
