import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from i18n_static import l10n_text

DEFAULT_STORAGE_CONFIG = {
    "refresh_seconds": 60,
    "storage_disk_warn_percent": 80.0,
    "storage_disk_critical_percent": 90.0,
    "storage_inode_warn_percent": 80.0,
    "storage_inode_critical_percent": 90.0,
    "storage_max_mounts": 24,
    "storage_include_tmpfs": False,
}

SEVERITY_RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SEVERITY_SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

PSEUDO_FS_TYPES = {
    "autofs",
    "binfmt_misc",
    "bpf",
    "cgroup",
    "cgroup2",
    "configfs",
    "debugfs",
    "devpts",
    "devtmpfs",
    "efivarfs",
    "fuse.portal",
    "fuse.gvfsd-fuse",
    "fusectl",
    "hugetlbfs",
    "mqueue",
    "nsfs",
    "overlay",
    "proc",
    "pstore",
    "ramfs",
    "rpc_pipefs",
    "securityfs",
    "squashfs",
    "sysfs",
    "tracefs",
}

NO_INODE_FS_TYPES = {
    "exfat",
    "fuseblk",
    "iso9660",
    "msdos",
    "ntfs",
    "ntfs3",
    "vfat",
}

TMPFS_TYPES = {"tmpfs"}

SKIP_MOUNT_PREFIXES = (
    "/boot/efi/EFI",
    "/dev",
    "/proc",
    "/run/docker",
    "/run/snapd",
    "/snap",
    "/sys",
    "/var/lib/docker/overlay2",
    "/var/lib/containers/storage/overlay",
)

STORAGE_TABLE_STYLE = """
<style id="storage-pulse-compact-table">
  .storage-table {
    min-width: 960px !important;
    table-layout: fixed;
  }
  .storage-table th,
  .storage-table td {
    padding: 11px 12px;
  }
  .storage-path,
  .storage-device {
    display: block;
    max-width: 190px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .storage-device {
    margin-top: 4px;
    color: var(--muted);
    font-size: 11px;
    opacity: 0.86;
  }
  .storage-size {
    display: grid;
    gap: 4px;
    min-width: 118px;
    font-size: 12px;
    line-height: 1.25;
  }
  .storage-size span {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    white-space: nowrap;
  }
  .storage-size small {
    color: var(--muted);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .storage-table .metric-row {
    min-width: 180px;
    grid-template-columns: 58px 46px minmax(70px, 1fr);
    gap: 8px;
  }
  .metric-na .metric-fill {
    background: var(--unknown);
    opacity: 0.28;
    box-shadow: none;
  }
  .storage-help {
    min-width: 190px;
    max-width: 260px;
    line-height: 1.42;
  }
  @media (max-width: 980px) {
    .storage-table {
      min-width: 900px !important;
    }
  }
</style>
""".strip()


@dataclass(frozen=True)
class MountEntry:
    device: str
    mount: str
    fs_type: str
    total: int | None
    used: int | None
    free: int | None
    used_percent: float | None
    inode_used: int | None
    inode_total: int | None
    inode_percent: float | None
    inode_supported: bool
    disk_level: str
    inode_level: str
    severity: str
    note: str


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_last_success(state_path):
    path = Path(state_path)
    if not path.exists():
        return "never"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "never"
    if isinstance(data, dict):
        return str(data.get("last_success_at") or "never")
    return "never"


def _write_last_success(state_path, value):
    Path(state_path).write_text(json.dumps({"last_success_at": value}, indent=2), encoding="utf-8")


def _load_config(config_path):
    config = dict(DEFAULT_STORAGE_CONFIG)
    if not config_path:
        return config
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError("PyYAML is required for config files.") from exc
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Config file must contain a mapping.")
    for key, value in loaded.items():
        if key in config:
            config[key] = value
    return config


def _decode_mount_field(value):
    return value.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")


def _read_mounts():
    path = Path("/proc/self/mounts")
    if not path.exists():
        return [("root", "/", "unknown")]

    mounts = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            device = _decode_mount_field(parts[0])
            mount = _decode_mount_field(parts[1])
            fs_type = parts[2]
            mounts.append((device, mount, fs_type))
    except Exception:
        return [("root", "/", "unknown")]
    return mounts


def _is_desktop_runtime_mount(mount):
    """Return True for per-user desktop helper mounts that are not storage health targets."""

    return bool(re.match(r"^/run/user/\d+/(doc|gvfs)(/|$)", mount))


def _should_skip_mount(device, mount, fs_type, config):
    if _is_desktop_runtime_mount(mount):
        return True
    if fs_type in PSEUDO_FS_TYPES:
        return True
    if fs_type in TMPFS_TYPES and not bool(config.get("storage_include_tmpfs", False)):
        return True
    if any(mount == prefix or mount.startswith(prefix + "/") for prefix in SKIP_MOUNT_PREFIXES):
        return True
    if mount.startswith("/var/lib/docker/containers/"):
        return True
    if mount.startswith("/var/lib/docker/overlay2/"):
        return True
    if device.startswith("overlay"):
        return True
    return False


def _level_percent(value, warn, critical, *, missing_as="unknown"):
    if value is None:
        return missing_as
    if value >= float(critical):
        return "critical"
    if value >= float(warn):
        return "warn"
    return "ok"


def _overall(levels):
    return max(levels or ["unknown"], key=lambda item: SEVERITY_RANK.get(item, 0))


def _collect_usage(mount):
    try:
        stats = os.statvfs(mount)
    except Exception:
        return None

    block_size = stats.f_frsize or stats.f_bsize or 1
    total = stats.f_blocks * block_size
    free = stats.f_bavail * block_size
    used = max(0, total - free)
    used_percent = None if total <= 0 else used / total * 100.0

    inode_total = stats.f_files
    inode_free = stats.f_ffree
    inode_used = None
    inode_percent = None
    if inode_total and inode_total > 0:
        inode_used = max(0, inode_total - inode_free)
        inode_percent = inode_used / inode_total * 100.0

    return total, used, free, used_percent, inode_used, inode_total, inode_percent


def _inode_supported(fs_type, inode_percent):
    if fs_type in NO_INODE_FS_TYPES and inode_percent is None:
        return False
    return True


def _note_for_entry(disk_level, inode_level, fs_type, inode_supported):
    if disk_level == "critical":
        return l10n_text(
            "Disk space is critically high. Free space soon or move data before writes start failing.",
            "Der Speicher ist kritisch voll. Schaffe bald Platz oder verschiebe Daten, bevor Schreibvorgänge fehlschlagen.",
        )
    if inode_level == "critical":
        return l10n_text(
            "Inodes are critically high. Too many small files can make a disk act full even when GB are still free.",
            "Inodes sind kritisch hoch. Zu viele kleine Dateien können eine Platte voll wirken lassen, obwohl noch GB frei sind.",
        )
    if disk_level == "warn":
        return l10n_text(
            "Disk usage is high. Plan cleanup or expansion before it becomes urgent.",
            "Die Speichernutzung ist hoch. Plane Aufräumen oder Erweiterung, bevor es dringend wird.",
        )
    if inode_level == "warn":
        return l10n_text(
            "Inode usage is high. This usually means many small files. Review caches, sessions, logs, or generated files.",
            "Die Inode-Nutzung ist hoch. Das bedeutet meist viele kleine Dateien. Prüfe Caches, Sessions, Logs oder generierte Dateien.",
        )
    if not inode_supported:
        return l10n_text(
            f"Looks healthy. This filesystem type ({fs_type}) does not report normal Linux inode usage, so inodes are shown as N/A.",
            f"Sieht gesund aus. Dieser Dateisystemtyp ({fs_type}) meldet keine normale Linux-Inode-Nutzung, deshalb werden Inodes als N/A angezeigt.",
        )
    if disk_level == "unknown" or inode_level == "unknown":
        return l10n_text(
            "Some storage values were unavailable on this mount. Review manually if this mount is important.",
            "Einige Speicherwerte waren für diesen Mount nicht verfügbar. Prüfe manuell, falls dieser Mount wichtig ist.",
        )
    return l10n_text(
        "Looks healthy. No cleanup action needed from Storage Pulse.",
        "Sieht gesund aus. Von Storage Pulse ist keine Aufräumaktion nötig.",
    )


def _entry_severity(disk_level, inode_level):
    return _overall([disk_level, inode_level])


def _collect_mount_entries(config):
    entries = []
    seen_mounts = set()
    for device, mount, fs_type in _read_mounts():
        if mount in seen_mounts:
            continue
        seen_mounts.add(mount)
        if _should_skip_mount(device, mount, fs_type, config):
            continue
        usage = _collect_usage(mount)
        if usage is None:
            entries.append(
                MountEntry(
                    device=device,
                    mount=mount,
                    fs_type=fs_type,
                    total=None,
                    used=None,
                    free=None,
                    used_percent=None,
                    inode_used=None,
                    inode_total=None,
                    inode_percent=None,
                    inode_supported=True,
                    disk_level="unknown",
                    inode_level="unknown",
                    severity="unknown",
                    note=l10n_text(
                        "Usage could not be read for this mount. If this is a virtual desktop mount, it can usually be ignored.",
                        "Die Nutzung konnte für diesen Mount nicht gelesen werden. Wenn das ein virtueller Desktop-Mount ist, kann er meistens ignoriert werden.",
                    ),
                )
            )
            continue

        total, used, free, used_percent, inode_used, inode_total, inode_percent = usage
        inode_supported = _inode_supported(fs_type, inode_percent)
        disk_level = _level_percent(used_percent, config["storage_disk_warn_percent"], config["storage_disk_critical_percent"])
        inode_level = _level_percent(
            inode_percent,
            config["storage_inode_warn_percent"],
            config["storage_inode_critical_percent"],
            missing_as="ok" if not inode_supported else "unknown",
        )
        entries.append(
            MountEntry(
                device=device,
                mount=mount,
                fs_type=fs_type,
                total=total,
                used=used,
                free=free,
                used_percent=used_percent,
                inode_used=inode_used,
                inode_total=inode_total,
                inode_percent=inode_percent,
                inode_supported=inode_supported,
                disk_level=disk_level,
                inode_level=inode_level,
                severity=_entry_severity(disk_level, inode_level),
                note=_note_for_entry(disk_level, inode_level, fs_type, inode_supported),
            )
        )

    entries.sort(key=_entry_sort_key)
    return entries[: max(1, int(config.get("storage_max_mounts", 24)))]


def _entry_sort_key(entry):
    important = 0 if entry.mount == "/" else 1
    return (
        SEVERITY_SORT.get(entry.severity, SEVERITY_SORT["unknown"]),
        important,
        entry.mount.count("/"),
        entry.mount,
    )


def _bytes_to_gib(value):
    if value is None:
        return "-"
    return f"{value / (1024 ** 3):.1f} GiB"


def _format_percent(value):
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _format_inode_percent(entry):
    if not entry.inode_supported:
        return "N/A"
    return _format_percent(entry.inode_percent)


def _format_inodes(entry):
    if not entry.inode_supported:
        return "N/A"
    used = entry.inode_used
    total = entry.inode_total
    if used is None or total is None:
        return "-"
    if total >= 1_000_000:
        return f"{used / 1_000_000:.1f}M / {total / 1_000_000:.1f}M"
    if total >= 1_000:
        return f"{used / 1_000:.1f}K / {total / 1_000:.1f}K"
    return f"{used} / {total}"


def _shorten_middle(value, max_len=34):
    if len(value) <= max_len:
        return value
    head = max(8, max_len // 2 - 2)
    tail = max(10, max_len - head - 3)
    return f"{value[:head]}...{value[-tail:]}"


def _path_block(primary, secondary):
    primary_safe = html.escape(primary)
    secondary_safe = html.escape(secondary)
    primary_short = html.escape(_shorten_middle(primary, 32))
    secondary_short = html.escape(_shorten_middle(secondary, 34))
    return (
        f"<code class='storage-path' title='{primary_safe}'>{primary_short}</code>"
        f"<code class='storage-device' title='{secondary_safe}'>{secondary_short}</code>"
    )


def _size_block(entry):
    return (
        "<div class='storage-size'>"
        f"<span><small>{l10n_text('Total', 'Gesamt')}</small><code>{html.escape(_bytes_to_gib(entry.total))}</code></span>"
        f"<span><small>{l10n_text('Used', 'Belegt')}</small><code>{html.escape(_bytes_to_gib(entry.used))}</code></span>"
        f"<span><small>{l10n_text('Free', 'Frei')}</small><code>{html.escape(_bytes_to_gib(entry.free))}</code></span>"
        "</div>"
    )


def _bar(label_html, value_text, percent, level):
    width = "0%" if percent is None else f"{max(0.0, min(float(percent), 100.0)):.1f}%"
    level_class = "na" if value_text == "N/A" else level
    return (
        f"<div class='metric-row metric-{html.escape(level_class)}'>"
        f"<span class='metric-label'>{label_html}</span>"
        f"<span class='metric-value'>{html.escape(value_text)}</span>"
        f"<span class='metric-track'><span class='metric-fill' style='width:{width}'></span></span>"
        "</div>"
    )


def _card(css_class, label_en, label_de, value, state):
    return (
        f"<div class='card {html.escape(css_class)}'>"
        f"<span>{l10n_text(label_en, label_de)}</span>"
        f"<strong>{html.escape(value)}</strong>"
        f"<small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small>"
        "</div>"
    )


def _summary_counts(entries):
    return {
        "total": len(entries),
        "ok": sum(1 for entry in entries if entry.severity == "ok"),
        "warn": sum(1 for entry in entries if entry.severity == "warn"),
        "critical": sum(1 for entry in entries if entry.severity == "critical"),
        "unknown": sum(1 for entry in entries if entry.severity == "unknown"),
    }


def _summary_cards(entries):
    counts = _summary_counts(entries)
    return "\n".join(
        [
            _card("card-total", "Mounts", "Mounts", str(counts["total"]), "ok" if counts["total"] else "unknown"),
            _card("card-ok", "OK", "OK", str(counts["ok"]), "ok"),
            _card("card-warn", "Review", "Prüfen", str(counts["warn"]), "warn" if counts["warn"] else "ok"),
            _card("card-critical", "Critical", "Kritisch", str(counts["critical"]), "critical" if counts["critical"] else "ok"),
            _card("card-unknown", "Unknown", "Unbekannt", str(counts["unknown"]), "unknown" if counts["unknown"] else "ok"),
        ]
    )


def _mount_row(entry):
    disk_bar = _bar(l10n_text("Disk", "Speicher"), _format_percent(entry.used_percent), entry.used_percent, entry.disk_level)
    inode_bar = _bar(l10n_text("Inodes", "Inodes"), _format_inode_percent(entry), entry.inode_percent, entry.inode_level)
    return (
        "<tr>"
        f"<td>{_path_block(entry.mount, entry.device)}</td>"
        f"<td><code>{html.escape(entry.fs_type)}</code></td>"
        f"<td>{_size_block(entry)}</td>"
        f"<td>{disk_bar}</td>"
        f"<td>{inode_bar}</td>"
        f"<td><code>{html.escape(_format_inodes(entry))}</code></td>"
        f"<td><span class='sev-badge sev-{html.escape(entry.severity)}'>{html.escape(entry.severity.upper())}</span></td>"
        f"<td class='storage-help'>{entry.note}</td>"
        "</tr>"
    )


def _overall_recommendation(overall):
    if overall == "critical":
        return l10n_text(
            "Storage needs attention now. A full disk or exhausted inodes can break apps, logs, databases, and updates.",
            "Speicher braucht jetzt Aufmerksamkeit. Eine volle Platte oder erschöpfte Inodes können Apps, Logs, Datenbanken und Updates kaputt machen.",
        )
    if overall == "warn":
        return l10n_text(
            "Storage is not failing, but one or more mounts should be reviewed before they become urgent.",
            "Speicher fällt nicht aus, aber ein oder mehrere Mounts sollten geprüft werden, bevor es dringend wird.",
        )
    if overall == "unknown":
        return l10n_text(
            "Some storage information could not be collected. Review important mounts manually if needed.",
            "Einige Speicherinformationen konnten nicht gesammelt werden. Prüfe wichtige Mounts bei Bedarf manuell.",
        )
    return l10n_text(
        "Storage looks healthy. No cleanup or repair action is suggested by this page.",
        "Speicher sieht gesund aus. Diese Seite schlägt keine Aufräum- oder Reparaturaktion vor.",
    )


def _plain_summary(entries):
    counts = _summary_counts(entries)
    return (
        '<section class="messages" aria-label="Storage plain summary">'
        f"<p><strong>{l10n_text('Plain meaning', 'Einfache Bedeutung')}</strong>: "
        f"{l10n_text('Disk usage shows how full a filesystem is. Inodes show whether there are too many small files.', 'Speichernutzung zeigt, wie voll ein Dateisystem ist. Inodes zeigen, ob es zu viele kleine Dateien gibt.')}</p>"
        f"<p>{l10n_text('Summary', 'Zusammenfassung')}: {counts['total']} Mounts · OK {counts['ok']} · WARN {counts['warn']} · CRITICAL {counts['critical']} · UNKNOWN {counts['unknown']}</p>"
        f"<p>{l10n_text('Virtual desktop and system helper mounts are hidden from this overview so normal users see the real storage targets first.', 'Virtuelle Desktop- und System-Hilfsmounts werden in dieser Übersicht ausgeblendet, damit normale Nutzer zuerst die echten Speicherziele sehen.')}</p>"
        f"<p>{l10n_text('Storage Pulse only observes. It does not delete files, clean caches, repair disks, or change mounts.', 'Storage Pulse beobachtet nur. Es löscht keine Dateien, leert keine Caches, repariert keine Platten und ändert keine Mounts.')}</p>"
        "</section>"
    )


def _storage_table(entries):
    if not entries:
        return f"""
      <section class="health-panel" aria-label="Storage notice">
        <div class="health-head">
          <h2>{l10n_text('Storage Overview', 'Speicherübersicht')}</h2>
          <span class="pill">{l10n_text('No mount data', 'Keine Mount-Daten')}</span>
        </div>
        <p class="recommendation">{l10n_text('No storage mount data was collected. This can happen on restricted platforms.', 'Es wurden keine Speicher-Mount-Daten gesammelt. Das kann auf eingeschränkten Plattformen passieren.')}</p>
      </section>
""".rstrip()

    rows = "\n".join(_mount_row(entry) for entry in entries)
    return f"""
      {STORAGE_TABLE_STYLE}
      <section class="health-panel" aria-label="Storage details">
        <div class="health-head">
          <h2>{l10n_text('Local Filesystems', 'Lokale Dateisysteme')}</h2>
          <span class="pill">{l10n_text('Read-only local inspection', 'Nur lesende lokale Prüfung')}</span>
        </div>
        {_plain_summary(entries)}
        <section class="table-shell" aria-label="Storage table">
          <table class="storage-table">
            <colgroup>
              <col style="width: 23%">
              <col style="width: 8%">
              <col style="width: 13%">
              <col style="width: 15%">
              <col style="width: 15%">
              <col style="width: 9%">
              <col style="width: 8%">
              <col style="width: 19%">
            </colgroup>
            <thead>
              <tr>
                <th>{l10n_text('Mount / device', 'Mount / Gerät')}</th>
                <th>{l10n_text('Type', 'Typ')}</th>
                <th>{l10n_text('Size', 'Größe')}</th>
                <th>{l10n_text('Disk usage', 'Speichernutzung')}</th>
                <th>{l10n_text('Inode usage', 'Inode-Nutzung')}</th>
                <th>{l10n_text('Inodes', 'Inodes')}</th>
                <th>{l10n_text('Severity', 'Status')}</th>
                <th>{l10n_text('Plain-English help', 'Einfache Erklärung')}</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </section>
      </section>
""".rstrip()


def _render(template_path, output_path, generated_at, previous_last_success, config, entries):
    overall = _overall([entry.severity for entry in entries])
    template = Path(template_path).read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": "STORAGE PULSE",
        "{{REFRESH_SECONDS}}": str(int(config.get("refresh_seconds", 60))),
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{LAST_SUCCESS_AT}}": html.escape(previous_last_success),
        "{{OVERALL}}": html.escape(overall.upper()),
        "{{OVERALL_CLASS}}": html.escape(overall),
        "{{RECOMMENDATION}}": _overall_recommendation(overall),
        "{{SUMMARY_CARDS}}": _summary_cards(entries),
        "{{STORAGE_TABLE}}": _storage_table(entries),
        "{{MESSAGES}}": f"<p>{l10n_text('No storage refresh warnings.', 'Keine Speicher-Aktualisierungswarnungen.')}</p>",
    }
    html_text = template
    for key, value in replacements.items():
        html_text = html_text.replace(key, value)
    Path(output_path).write_text(html_text, encoding="utf-8")


def generate_storage_pulse(
    output_path="storage.html",
    template_path="storage_template.html",
    config_path=None,
    state_path=".storage_pulse_state.json",
):
    generated_at = _now()
    previous_last_success = _read_last_success(state_path)
    config = dict(DEFAULT_STORAGE_CONFIG)
    try:
        config = _load_config(config_path)
        entries = _collect_mount_entries(config)
        _render(template_path, output_path, generated_at, previous_last_success, config, entries)
        _write_last_success(state_path, generated_at)
        return True
    except Exception as exc:
        _render(template_path, output_path, generated_at, previous_last_success, config, [])
        path = Path(output_path)
        if path.exists():
            html_text = path.read_text(encoding="utf-8")
            error = l10n_text(f"Storage refresh failed: {exc}", f"Speicher-Aktualisierung fehlgeschlagen: {exc}")
            html_text = html_text.replace(
                f"<p>{l10n_text('No storage refresh warnings.', 'Keine Speicher-Aktualisierungswarnungen.')}</p>",
                f"<p>{error}</p>",
            )
            path.write_text(html_text, encoding="utf-8")
        return False
