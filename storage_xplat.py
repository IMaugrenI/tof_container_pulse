import html
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from i18n_static import l10n_text
from platform_support import list_windows_drives, os_family, run_command, run_powershell
from storage import generate_storage_pulse as generate_linux_storage_pulse

DEFAULT_CONFIG = {"refresh_seconds": 60, "storage_disk_warn_percent": 80.0, "storage_disk_critical_percent": 90.0}
RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

@dataclass(frozen=True)
class Volume:
    name: str
    device: str
    fs_type: str
    total: int | None
    used: int | None
    free: int | None
    percent: float | None
    severity: str
    note: str


def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _last(path):
    p=Path(path)
    if not p.exists(): return "never"
    try:
        data=json.loads(p.read_text(encoding='utf-8')); return str(data.get('last_success_at') or 'never') if isinstance(data,dict) else 'never'
    except Exception: return "never"

def _save(path,value): Path(path).write_text(json.dumps({'last_success_at':value},indent=2),encoding='utf-8')

def _cfg(config_path):
    config=dict(DEFAULT_CONFIG)
    if config_path and Path(config_path).exists():
        try:
            import yaml
            data=yaml.safe_load(Path(config_path).read_text(encoding='utf-8')) or {}
            if isinstance(data,dict): config.update({k:v for k,v in data.items() if k in config})
        except Exception: pass
    return config

def _pct(used,total):
    if used is None or total is None or total<=0: return None
    return max(0.0,min(100.0,used/total*100.0))

def _level(value,config):
    if value is None: return 'unknown'
    if value>=float(config['storage_disk_critical_percent']): return 'critical'
    if value>=float(config['storage_disk_warn_percent']): return 'warn'
    return 'ok'

def _fmt_bytes(v): return '-' if v is None else f"{v/(1024**3):.1f} GiB"

def _fmt_pct(v): return '-' if v is None else f"{v:.1f}%"

def _collect_with_psutil(config):
    try: import psutil
    except Exception: return None
    vols=[]
    try:
        for part in psutil.disk_partitions(all=False):
            try: usage=psutil.disk_usage(part.mountpoint)
            except Exception: continue
            sev=_level(float(usage.percent),config)
            vols.append(Volume(part.mountpoint,part.device or part.mountpoint,part.fstype or '-',usage.total,usage.used,usage.free,float(usage.percent),sev,_note(sev, part.fstype or '-')))
    except Exception: return None
    return vols

def _collect_macos(config):
    vols=[]
    res=run_command(['df','-kP'],timeout=2.0)
    if res.code!=0: return vols
    for line in res.stdout.splitlines()[1:]:
        parts=line.split()
        if len(parts)<6: continue
        dev,total,used,free,mount=parts[0],parts[1],parts[2],parts[3],parts[5]
        try:
            total_i=int(total)*1024; used_i=int(used)*1024; free_i=int(free)*1024
        except Exception: continue
        p=_pct(used_i,total_i); sev=_level(p,config)
        vols.append(Volume(mount,dev,'-',total_i,used_i,free_i,p,sev,_note(sev,'-')))
    return vols

def _collect_windows(config):
    vols=[]
    try:
        for drive in list_windows_drives():
            try: u=shutil.disk_usage(drive)
            except Exception: continue
            p=_pct(u.used,u.total); sev=_level(p,config)
            vols.append(Volume(drive,drive,'drive',u.total,u.used,u.free,p,sev,_note(sev,'drive')))
    except Exception: pass
    if vols: return vols
    ps=run_powershell("Get-PSDrive -PSProvider FileSystem | ForEach-Object {\"$($_.Name):,$($_.Used),$($_.Free)\"}",timeout=3)
    if ps.code==0:
        for line in ps.stdout.splitlines():
            parts=[p.strip() for p in line.split(',')]
            if len(parts)<3: continue
            try:
                used=int(float(parts[1] or 0)); free=int(float(parts[2] or 0)); total=used+free
            except Exception: continue
            p=_pct(used,total); sev=_level(p,config)
            vols.append(Volume(parts[0]+'\\',parts[0]+'\\','drive',total,used,free,p,sev,_note(sev,'drive')))
    return vols

def _note(sev,fs):
    if sev=='critical': return l10n_text('Storage is critically full. Free space or expand soon.', 'Speicher ist kritisch voll. Bald Platz schaffen oder erweitern.')
    if sev=='warn': return l10n_text('Storage usage is high. Plan cleanup or expansion.', 'Speichernutzung ist hoch. Aufräumen oder Erweiterung planen.')
    if sev=='unknown': return l10n_text('Storage values could not be fully read on this platform.', 'Speicherwerte konnten auf dieser Plattform nicht vollständig gelesen werden.')
    return l10n_text('Looks healthy. Storage Pulse did not change anything.', 'Sieht gesund aus. Storage Pulse hat nichts geändert.')

def _overall(vols): return max((v.severity for v in vols),key=lambda s:RANK.get(s,0)) if vols else 'unknown'

def _card(cls,en,de,val,state): return f"<div class='card {cls}'><span>{l10n_text(en,de)}</span><strong>{html.escape(str(val))}</strong><small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small></div>"

def _cards(vols):
    total=len(vols); ok=sum(v.severity=='ok' for v in vols); warn=sum(v.severity=='warn' for v in vols); crit=sum(v.severity=='critical' for v in vols); unk=sum(v.severity=='unknown' for v in vols)
    return '\n'.join([_card('card-total','Volumes','Volumes',total,'ok' if total else 'unknown'),_card('card-ok','OK','OK',ok,'ok'),_card('card-warn','Review','Prüfen',warn,'warn' if warn else 'ok'),_card('card-critical','Critical','Kritisch',crit,'critical' if crit else 'ok'),_card('card-unknown','Unknown','Unbekannt',unk,'unknown' if unk else 'ok')])

def _bar(label,value,pct,level):
    width='0%' if pct is None else f"{max(0,min(float(pct),100)):.1f}%"
    return f"<div class='metric-row metric-{html.escape(level)}'><span class='metric-label'>{label}</span><span class='metric-value'>{html.escape(value)}</span><span class='metric-track'><span class='metric-fill' style='width:{width}'></span></span></div>"

def _table(vols):
    if not vols:
        return f"<section class='health-panel'><div class='health-head'><h2>{l10n_text('Storage Overview','Speicherübersicht')}</h2><span class='pill'>{l10n_text('No volume data','Keine Volume-Daten')}</span></div><p class='recommendation'>{l10n_text('No storage volume data was collected on this platform.','Auf dieser Plattform wurden keine Storage-Volume-Daten gesammelt.')}</p></section>"
    rows=''.join(f"<tr><td><code>{html.escape(v.name)}</code><code class='storage-device'>{html.escape(v.device)}</code></td><td><code>{html.escape(v.fs_type)}</code></td><td><div class='storage-size'><span><small>{l10n_text('Total','Gesamt')}</small><code>{_fmt_bytes(v.total)}</code></span><span><small>{l10n_text('Used','Belegt')}</small><code>{_fmt_bytes(v.used)}</code></span><span><small>{l10n_text('Free','Frei')}</small><code>{_fmt_bytes(v.free)}</code></span></div></td><td>{_bar(l10n_text('Disk','Speicher'),_fmt_pct(v.percent),v.percent,v.severity)}</td><td>{_bar('Inodes','N/A',None,'unknown')}</td><td><code>N/A</code></td><td><span class='sev-badge sev-{v.severity}'>{v.severity.upper()}</span></td><td class='storage-help'>{v.note}</td></tr>" for v in vols)
    style="<style>.storage-table{min-width:900px!important}.storage-device{display:block;color:var(--muted);font-size:11px;margin-top:4px}.storage-size{display:grid;gap:4px}.storage-size span{display:flex;justify-content:space-between;gap:8px}.storage-help{min-width:180px}</style>"
    return f"{style}<section class='health-panel'><div class='health-head'><h2>{l10n_text('Local Volumes','Lokale Volumes')}</h2><span class='pill'>{l10n_text('Cross-platform read-only inspection','Plattformübergreifende Nur-Lese-Prüfung')}</span></div><section class='messages'><p>{l10n_text('Storage Pulse observes disk usage only. It does not delete, clean, repair, or change mounts.','Storage Pulse beobachtet nur Speichernutzung. Es löscht, bereinigt, repariert oder ändert keine Mounts.')}</p></section><section class='table-shell'><table class='storage-table'><thead><tr><th>{l10n_text('Mount / device','Mount / Gerät')}</th><th>{l10n_text('Type','Typ')}</th><th>{l10n_text('Size','Größe')}</th><th>{l10n_text('Disk usage','Speichernutzung')}</th><th>{l10n_text('Inode usage','Inode-Nutzung')}</th><th>{l10n_text('Inodes','Inodes')}</th><th>{l10n_text('Severity','Status')}</th><th>{l10n_text('Plain-English help','Einfache Erklärung')}</th></tr></thead><tbody>{rows}</tbody></table></section></section>"

def _render(template_path,output_path,generated,previous,config,vols):
    overall=_overall(vols); text=Path(template_path).read_text(encoding='utf-8')
    rec=l10n_text('Cross-platform storage data was collected where available. Inode details are Linux-first and may show N/A on macOS or Windows.','Plattformübergreifende Speicherdaten wurden gesammelt, soweit verfügbar. Inode-Details sind Linux-first und können auf macOS oder Windows N/A zeigen.')
    for k,v in {"{{TITLE}}":"STORAGE PULSE","{{REFRESH_SECONDS}}":str(int(config.get('refresh_seconds',60))),"{{GENERATED_AT}}":html.escape(generated),"{{LAST_SUCCESS_AT}}":html.escape(previous),"{{OVERALL}}":overall.upper(),"{{OVERALL_CLASS}}":overall,"{{RECOMMENDATION}}":rec,"{{SUMMARY_CARDS}}":_cards(vols),"{{STORAGE_TABLE}}":_table(vols),"{{MESSAGES}}":f"<p>{l10n_text('No storage refresh warnings.','Keine Speicher-Aktualisierungswarnungen.')}</p>"}.items(): text=text.replace(k,v)
    Path(output_path).write_text(text,encoding='utf-8')

def generate_storage_pulse(output_path='storage.html',template_path='storage_template.html',config_path=None,state_path='.storage_pulse_state.json'):
    if os_family()=='linux': return generate_linux_storage_pulse(output_path=output_path,template_path=template_path,config_path=config_path,state_path=state_path)
    generated=_now(); previous=_last(state_path); config=_cfg(config_path)
    try:
        vols=_collect_with_psutil(config)
        if vols is None: vols=_collect_windows(config) if os_family()=='windows' else _collect_macos(config) if os_family()=='macos' else []
        _render(template_path,output_path,generated,previous,config,vols); _save(state_path,generated); return True
    except Exception:
        _render(template_path,output_path,generated,previous,config,[]); return False
