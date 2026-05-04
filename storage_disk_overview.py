"""Read-only disk overview renderer for Storage Pulse.

This module intentionally shows a privacy-safe orientation layer:
real disks, partitions, LVM-style devices, sizes, and mountpoints.
It does not display serial numbers, UUIDs, WWN, or model names.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
from dataclasses import dataclass, field

from i18n_static import l10n_text

LSBLK_TIMEOUT_SECONDS = 2.0
VISIBLE_TYPES = {"disk", "part", "lvm", "crypt", "raid0", "raid1", "raid5", "raid6", "raid10"}
HIDDEN_TYPES = {"loop", "rom"}

DISK_OVERVIEW_STYLE = """
<style id="storage-pulse-disk-overview">
  .disk-overview-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(140px, 1fr));
    gap: 12px;
    margin: 12px 0;
  }
  .disk-mini-card {
    border: 1px solid rgba(151, 167, 189, 0.16);
    border-radius: 16px;
    padding: 12px 14px;
    background: var(--panel-softer);
  }
  .disk-mini-card span {
    display: block;
    color: var(--muted);
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .disk-mini-card strong {
    display: block;
    margin-top: 6px;
    color: var(--text-strong);
    font-size: 24px;
    line-height: 1;
    letter-spacing: -0.045em;
  }
  .disk-tree {
    display: grid;
    gap: 8px;
    margin-top: 12px;
  }
  .disk-row {
    display: grid;
    grid-template-columns: minmax(180px, 1.1fr) 92px 82px minmax(120px, 0.9fr) minmax(190px, 1.1fr);
    gap: 12px;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid rgba(151, 167, 189, 0.13);
    border-radius: 14px;
    background: rgba(8, 15, 27, 0.38);
  }
  body.light .disk-row {
    background: rgba(255, 255, 255, 0.48);
  }
  .disk-row.child {
    margin-left: 26px;
  }
  .disk-name {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .disk-glyph {
    flex: 0 0 auto;
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    border-radius: 9px;
    border: 1px solid rgba(54, 243, 211, 0.24);
    color: var(--teal);
    background: rgba(54, 243, 211, 0.08);
    font-weight: 900;
    font-size: 12px;
  }
  .disk-name code,
  .disk-mounts code {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .disk-label {
    color: var(--muted);
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .disk-value {
    color: var(--code-text);
    font-family: var(--mono);
    font-size: 12px;
  }
  .disk-help-text {
    color: var(--muted);
    line-height: 1.5;
  }
  @media (max-width: 980px) {
    .disk-overview-grid {
      grid-template-columns: 1fr;
    }
    .disk-row {
      grid-template-columns: 1fr 1fr;
    }
    .disk-row.child {
      margin-left: 12px;
    }
  }
</style>
""".strip()


@dataclass(frozen=True)
class DiskNode:
    name: str
    path: str
    node_type: str
    size: int | None
    fs_type: str
    mountpoints: tuple[str, ...]
    rota: str
    children: tuple["DiskNode", ...] = field(default_factory=tuple)


def _run_lsblk(columns: str):
    command = ["lsblk", "-J", "-b", "-o", columns]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=LSBLK_TIMEOUT_SECONDS, check=False)
    except Exception:
        return None


def _collect_lsblk_json():
    if not shutil.which("lsblk"):
        return None

    preferred = _run_lsblk("NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,PKNAME,ROTA")
    if preferred and preferred.returncode == 0:
        try:
            return json.loads(preferred.stdout)
        except Exception:
            return None

    fallback = _run_lsblk("NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINT,PKNAME,ROTA")
    if fallback and fallback.returncode == 0:
        try:
            return json.loads(fallback.stdout)
        except Exception:
            return None
    return None


def _mountpoints(raw):
    value = raw.get("mountpoints")
    if value is None:
        value = raw.get("mountpoint")
    if value is None:
        return tuple()
    if isinstance(value, list):
        return tuple(str(item) for item in value if item)
    if isinstance(value, str) and value:
        return (value,)
    return tuple()


def _parse_node(raw) -> DiskNode | None:
    node_type = str(raw.get("type") or "unknown")
    if node_type in HIDDEN_TYPES:
        return None

    children = []
    for child in raw.get("children") or []:
        parsed = _parse_node(child)
        if parsed is not None:
            children.append(parsed)

    if node_type not in VISIBLE_TYPES and not children:
        return None

    size = raw.get("size")
    try:
        size = int(size) if size is not None else None
    except Exception:
        size = None

    return DiskNode(
        name=str(raw.get("name") or raw.get("path") or "unknown"),
        path=str(raw.get("path") or raw.get("name") or "unknown"),
        node_type=node_type,
        size=size,
        fs_type=str(raw.get("fstype") or "-"),
        mountpoints=_mountpoints(raw),
        rota=str(raw.get("rota") if raw.get("rota") is not None else "-"),
        children=tuple(children),
    )


def _collect_disk_nodes():
    data = _collect_lsblk_json()
    if not isinstance(data, dict):
        return tuple()

    nodes = []
    for raw in data.get("blockdevices") or []:
        parsed = _parse_node(raw)
        if parsed is not None:
            nodes.append(parsed)
    return tuple(nodes)


def _flatten(nodes):
    result = []
    for node in nodes:
        result.append(node)
        result.extend(_flatten(node.children))
    return result


def _format_size(value):
    if value is None:
        return "-"
    if value >= 1024 ** 4:
        return f"{value / (1024 ** 4):.1f} TiB"
    return f"{value / (1024 ** 3):.1f} GiB"


def _type_label(node_type):
    labels = {
        "disk": ("disk", "Datenträger"),
        "part": ("partition", "Partition"),
        "lvm": ("LVM volume", "LVM-Volume"),
        "crypt": ("encrypted layer", "verschlüsselte Ebene"),
        "raid0": ("RAID device", "RAID-Gerät"),
        "raid1": ("RAID device", "RAID-Gerät"),
        "raid5": ("RAID device", "RAID-Gerät"),
        "raid6": ("RAID device", "RAID-Gerät"),
        "raid10": ("RAID device", "RAID-Gerät"),
    }
    return l10n_text(*labels.get(node_type, (node_type, node_type)))


def _media_label(node: DiskNode):
    if node.node_type != "disk":
        return _type_label(node.node_type)
    if node.rota == "0":
        return l10n_text("SSD/NVMe-style disk", "SSD/NVMe-artiger Datenträger")
    if node.rota == "1":
        return l10n_text("rotating disk", "rotierende Festplatte")
    return l10n_text("disk", "Datenträger")


def _mount_label(node: DiskNode):
    if not node.mountpoints:
        return "-"
    return ", ".join(node.mountpoints)


def _row(node: DiskNode, depth: int):
    child_class = " child" if depth else ""
    glyph = "D" if node.node_type == "disk" else "└"
    name = html.escape(node.name)
    path = html.escape(node.path)
    mounts = html.escape(_mount_label(node))
    fs_type = html.escape(node.fs_type or "-")
    return (
        f"<div class='disk-row{child_class}'>"
        f"<div class='disk-name'><span class='disk-glyph'>{glyph}</span><code title='{path}'>{name}</code></div>"
        f"<div><span class='disk-label'>{l10n_text('Type', 'Typ')}</span><div class='disk-value'>{_type_label(node.node_type)}</div></div>"
        f"<div><span class='disk-label'>{l10n_text('Size', 'Größe')}</span><div class='disk-value'>{html.escape(_format_size(node.size))}</div></div>"
        f"<div><span class='disk-label'>{l10n_text('Filesystem', 'Dateisystem')}</span><div class='disk-value'>{fs_type}</div></div>"
        f"<div class='disk-mounts'><span class='disk-label'>{l10n_text('Used at', 'Genutzt unter')}</span><code title='{mounts}'>{mounts}</code></div>"
        "</div>"
    )


def _rows(nodes, depth=0):
    result = []
    for node in nodes:
        result.append(_row(node, depth))
        result.extend(_rows(node.children, depth + 1))
    return result


def _summary(nodes):
    flat = _flatten(nodes)
    disk_count = sum(1 for node in flat if node.node_type == "disk")
    part_count = sum(1 for node in flat if node.node_type == "part")
    lvm_count = sum(1 for node in flat if node.node_type == "lvm")
    mounted_count = sum(1 for node in flat if node.mountpoints)
    total_disk_size = sum(node.size or 0 for node in flat if node.node_type == "disk")
    return {
        "disk_count": disk_count,
        "part_count": part_count,
        "lvm_count": lvm_count,
        "mounted_count": mounted_count,
        "total_disk_size": total_disk_size,
    }


def _mini_card(label_en, label_de, value):
    return (
        "<div class='disk-mini-card'>"
        f"<span>{l10n_text(label_en, label_de)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        "</div>"
    )


def render_disk_overview():
    nodes = _collect_disk_nodes()
    if not nodes:
        return f"""
      <section class="health-panel" aria-label="Disk overview">
        <div class="health-head">
          <h2>{l10n_text('Disk Overview', 'Datenträger-Übersicht')}</h2>
          <span class="pill">{l10n_text('Optional orientation layer', 'Optionale Orientierungsebene')}</span>
        </div>
        <p class="recommendation">{l10n_text('No disk tree was collected. Storage Pulse can still show mounted filesystems below.', 'Es wurde keine Datenträgerstruktur gesammelt. Storage Pulse kann unten trotzdem eingehängte Dateisysteme anzeigen.')}</p>
      </section>
""".rstrip()

    summary = _summary(nodes)
    rows = "\n".join(_rows(nodes))
    return f"""
      {DISK_OVERVIEW_STYLE}
      <section class="health-panel" aria-label="Disk overview">
        <div class="health-head">
          <h2>{l10n_text('Disk Overview', 'Datenträger-Übersicht')}</h2>
          <span class="pill">{l10n_text('Read-only lsblk view', 'Nur lesende lsblk-Ansicht')}</span>
        </div>
        <section class="disk-overview-grid" aria-label="Disk overview summary">
          {_mini_card('Disks', 'Datenträger', summary['disk_count'])}
          {_mini_card('Partitions', 'Partitionen', summary['part_count'])}
          {_mini_card('Mounted targets', 'Eingehängte Ziele', summary['mounted_count'])}
        </section>
        <section class="messages" aria-label="Disk overview explanation">
          <p><strong>{l10n_text('Plain meaning', 'Einfache Bedeutung')}</strong>: {l10n_text('A disk is the real SSD/HDD device. A partition is one area on that disk. A mountpoint is where Linux uses that area, for example /, /boot, or /boot/efi.', 'Ein Datenträger ist die echte SSD/HDD. Eine Partition ist ein Bereich auf diesem Datenträger. Ein Mountpoint ist der Ort, an dem Linux diesen Bereich nutzt, zum Beispiel /, /boot oder /boot/efi.')}</p>
          <p>{l10n_text('Serial numbers, UUIDs, WWN, and model names are not shown to keep screenshots safer.', 'Seriennummern, UUIDs, WWN und Modellnamen werden nicht angezeigt, damit Screenshots sicherer bleiben.')}</p>
        </section>
        <section class="disk-tree" aria-label="Disk tree">
          {rows}
        </section>
      </section>
""".rstrip()
