import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from i18n_static import l10n_text
from platform_support import command_exists, home_ssh_dir, os_family, run_command, run_powershell, safe_stat_mode
from security_v3 import generate_security_pulse as generate_linux_security_pulse

DEFAULT_CONFIG = {"refresh_seconds": 60, "security_command_timeout_seconds": 2.0}
RANK = {"ok": 0, "unknown": 1, "warn": 2, "critical": 3}
SORT = {"critical": 0, "warn": 1, "unknown": 2, "ok": 3}

@dataclass(frozen=True)
class Signal:
    name: str
    area: str
    value: str
    state: str
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

def _sig(en,de,area_en,area_de,value,state,severity,note_en,note_de):
    return Signal(l10n_text(en,de),l10n_text(area_en,area_de),str(value),l10n_text(state,state),severity,l10n_text(note_en,note_de))

def _ssh_hygiene():
    ssh=home_ssh_dir()
    if not ssh.exists():
        return _sig('SSH key hygiene','SSH-Key-Hygiene','Login','Login','no .ssh','optional','ok','No .ssh directory was found for the current user.','Für den aktuellen Nutzer wurde kein .ssh-Verzeichnis gefunden.')
    checked=suspicious=0
    try:
        for path in ssh.iterdir():
            if not path.is_file() or path.name.endswith('.pub') or path.name in {'known_hosts','config'}: continue
            checked+=1; mode=safe_stat_mode(path)
            if mode is not None and mode & 0o077: suspicious+=1
        auth=ssh/'authorized_keys'
        if auth.exists():
            checked+=1; mode=safe_stat_mode(auth)
            if mode is not None and mode & 0o022: suspicious+=1
    except Exception:
        return _sig('SSH key hygiene','SSH-Key-Hygiene','Login','Login','unreadable','unknown','unknown','Current-user SSH files could not be reviewed. No contents were shown.','SSH-Dateien des aktuellen Nutzers konnten nicht geprüft werden. Es wurden keine Inhalte angezeigt.')
    if suspicious:
        return _sig('SSH key hygiene','SSH-Key-Hygiene','Login','Login',f'{suspicious}/{checked}','review','warn','Some current-user SSH files appear more open than expected. File names and contents are not shown.','Einige SSH-Dateien des aktuellen Nutzers wirken offener als erwartet. Dateinamen und Inhalte werden nicht angezeigt.')
    return _sig('SSH key hygiene','SSH-Key-Hygiene','Login','Login',f'{checked} checked','calm','ok','Current-user SSH file permissions look calm. Key names and contents are not shown.','Die SSH-Dateirechte des aktuellen Nutzers wirken ruhig. Schlüssel-Namen und Inhalte werden nicht angezeigt.')

def _docker_visibility(config):
    timeout=float(config.get('security_command_timeout_seconds',2.0))
    if not command_exists('docker'):
        return _sig('Docker visibility','Docker-Sichtbarkeit','Containers','Container','docker not found','optional','ok','Docker CLI was not detected on this platform.','Docker CLI wurde auf dieser Plattform nicht erkannt.')
    res=run_command(['docker','ps','-q'],timeout=timeout)
    if res.code!=0:
        return _sig('Docker visibility','Docker-Sichtbarkeit','Containers','Container','unavailable','unknown','unknown','Docker CLI exists but running containers could not be read.','Docker CLI existiert, aber laufende Container konnten nicht gelesen werden.')
    count=len([l for l in res.stdout.splitlines() if l.strip()])
    return _sig('Docker visibility','Docker-Sichtbarkeit','Containers','Container',count,'present','ok','Docker CLI responded to a read-only container list request.','Docker CLI hat auf eine nur lesende Containerlisten-Abfrage geantwortet.')

def _mac_firewall(config):
    res=run_command(['/usr/libexec/ApplicationFirewall/socketfilterfw','--getglobalstate'],timeout=float(config.get('security_command_timeout_seconds',2.0)))
    if res.code!=0:
        return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk','unavailable','optional','ok','macOS firewall status was not readable with the standard local tool.','macOS-Firewallstatus war mit dem üblichen lokalen Werkzeug nicht lesbar.')
    text=res.stdout.lower()
    if 'enabled' in text:
        return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk','macOS firewall enabled','active','ok','macOS application firewall reports enabled. No rule was changed.','Die macOS-Application-Firewall meldet aktiv. Es wurde keine Regel verändert.')
    if 'disabled' in text:
        return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk','macOS firewall disabled','review','warn','macOS application firewall reports disabled. This can be intentional, but review if this host is exposed.','Die macOS-Application-Firewall meldet inaktiv. Das kann beabsichtigt sein, sollte aber bei exponierten Hosts geprüft werden.')
    return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk','macOS firewall unknown','optional','ok','macOS firewall responded, but the state was not classified.','macOS-Firewall hat geantwortet, aber der Status wurde nicht eingeordnet.')

def _mac_filevault(config):
    res=run_command(['fdesetup','status'],timeout=float(config.get('security_command_timeout_seconds',2.0)))
    if res.code!=0:
        return _sig('FileVault visibility','FileVault-Sichtbarkeit','Protection','Schutz','unavailable','optional','ok','FileVault status was not readable. No setting was changed.','FileVault-Status war nicht lesbar. Es wurde nichts verändert.')
    text=res.stdout.lower()
    if 'on' in text:
        return _sig('FileVault visibility','FileVault-Sichtbarkeit','Protection','Schutz','on','active','ok','FileVault appears enabled.','FileVault wirkt aktiv.')
    if 'off' in text:
        return _sig('FileVault visibility','FileVault-Sichtbarkeit','Protection','Schutz','off','review','warn','FileVault appears disabled. Review if disk encryption is expected.','FileVault wirkt deaktiviert. Prüfe, ob Festplattenverschlüsselung erwartet ist.')
    return _sig('FileVault visibility','FileVault-Sichtbarkeit','Protection','Schutz','unknown','optional','ok','FileVault responded, but the state was not classified.','FileVault hat geantwortet, aber der Status wurde nicht eingeordnet.')

def _mac_sip(config):
    res=run_command(['csrutil','status'],timeout=float(config.get('security_command_timeout_seconds',2.0)))
    if res.code!=0:
        return _sig('SIP visibility','SIP-Sichtbarkeit','Protection','Schutz','unavailable','optional','ok','System Integrity Protection status was not readable in this environment.','System-Integrity-Protection-Status war in dieser Umgebung nicht lesbar.')
    text=res.stdout.lower()
    if 'enabled' in text:
        return _sig('SIP visibility','SIP-Sichtbarkeit','Protection','Schutz','enabled','active','ok','System Integrity Protection appears enabled.','System Integrity Protection wirkt aktiv.')
    if 'disabled' in text:
        return _sig('SIP visibility','SIP-Sichtbarkeit','Protection','Schutz','disabled','review','warn','System Integrity Protection appears disabled. Review if this is intentional.','System Integrity Protection wirkt deaktiviert. Prüfe, ob das beabsichtigt ist.')
    return _sig('SIP visibility','SIP-Sichtbarkeit','Protection','Schutz','unknown','optional','ok','SIP status was not classified.','SIP-Status wurde nicht eingeordnet.')

def _windows_firewall(config):
    ps=run_powershell("Get-NetFirewallProfile | ForEach-Object {\"$($_.Name):$($_.Enabled)\"}",timeout=float(config.get('security_command_timeout_seconds',2.0))+2)
    if ps.code!=0:
        return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk','unavailable','unknown','unknown','Windows Firewall profile status could not be read.','Windows-Firewallprofilstatus konnte nicht gelesen werden.')
    lines=[l for l in ps.stdout.splitlines() if l.strip()]
    enabled=sum(l.lower().endswith(':true') for l in lines)
    disabled=sum(l.lower().endswith(':false') for l in lines)
    if disabled:
        return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk',f'{enabled} on / {disabled} off','review','warn','One or more Windows Firewall profiles appear disabled. Review if this is intended.','Ein oder mehrere Windows-Firewallprofile wirken deaktiviert. Prüfe, ob das beabsichtigt ist.')
    return _sig('Firewall visibility','Firewall-Sichtbarkeit','Network','Netzwerk',f'{enabled} on','active','ok','Windows Firewall profiles appear enabled. No rule was changed.','Windows-Firewallprofile wirken aktiv. Es wurde keine Regel verändert.')

def _windows_defender(config):
    ps=run_powershell("$s=Get-MpComputerStatus; \"RealTime:$($s.RealTimeProtectionEnabled),Antivirus:$($s.AntivirusEnabled)\"",timeout=float(config.get('security_command_timeout_seconds',2.0))+2)
    if ps.code!=0:
        return _sig('Defender visibility','Defender-Sichtbarkeit','Protection','Schutz','unavailable','optional','ok','Microsoft Defender status was not readable. This can be normal on some editions or policies.','Microsoft-Defender-Status war nicht lesbar. Das kann bei manchen Editionen oder Richtlinien normal sein.')
    text=ps.stdout.lower()
    if 'realtime:true' in text or 'antivirus:true' in text:
        return _sig('Defender visibility','Defender-Sichtbarkeit','Protection','Schutz','enabled','active','ok','Microsoft Defender appears enabled.','Microsoft Defender wirkt aktiv.')
    return _sig('Defender visibility','Defender-Sichtbarkeit','Protection','Schutz','review','review','warn','Microsoft Defender did not clearly report enabled protection. Review manually.','Microsoft Defender hat keinen klar aktiven Schutz gemeldet. Bitte manuell prüfen.')

def _windows_bitlocker(config):
    ps=run_powershell("Get-BitLockerVolume | Select-Object -First 1 -ExpandProperty ProtectionStatus",timeout=float(config.get('security_command_timeout_seconds',2.0))+2)
    if ps.code!=0:
        return _sig('BitLocker visibility','BitLocker-Sichtbarkeit','Protection','Schutz','unavailable','optional','ok','BitLocker status was not readable. No setting was changed.','BitLocker-Status war nicht lesbar. Es wurde nichts verändert.')
    value=ps.stdout.strip().lower()
    if 'on' in value or value=='1':
        return _sig('BitLocker visibility','BitLocker-Sichtbarkeit','Protection','Schutz','on','active','ok','BitLocker protection appears enabled for at least one volume.','BitLocker-Schutz wirkt für mindestens ein Volume aktiv.')
    return _sig('BitLocker visibility','BitLocker-Sichtbarkeit','Protection','Schutz',value or 'unknown','optional','ok','BitLocker status was collected as orientation only.','BitLocker-Status wurde nur als Orientierung gesammelt.')

def _collect(config):
    fam=os_family(); signals=[_sig('Platform identity','Plattform-Identität','Context','Kontext',fam,'ok','ok','Operating system context for this snapshot.','Betriebssystem-Kontext für diesen Schnappschuss.'), _ssh_hygiene(), _docker_visibility(config)]
    if fam=='macos': signals.extend([_mac_firewall(config),_mac_filevault(config),_mac_sip(config)])
    elif fam=='windows': signals.extend([_windows_firewall(config),_windows_defender(config),_windows_bitlocker(config)])
    else: signals.append(_sig('Platform support','Plattform-Unterstützung','Context','Kontext',fam,'optional','ok','This non-Linux platform has only baseline security orientation.','Diese Nicht-Linux-Plattform hat nur Basis-Sicherheitsorientierung.'))
    return sorted(signals,key=lambda s:(SORT.get(s.severity,9),s.area,s.name))

def _overall(signals): return max((s.severity for s in signals),key=lambda x:RANK.get(x,0)) if signals else 'unknown'

def _card(cls,en,de,val,state): return f"<div class='card {cls}'><span>{l10n_text(en,de)}</span><strong>{html.escape(str(val))}</strong><small class='state state-{html.escape(state)}'>{html.escape(state.upper())}</small></div>"

def _cards(signals):
    total=len(signals); ok=sum(s.severity=='ok' for s in signals); warn=sum(s.severity=='warn' for s in signals); crit=sum(s.severity=='critical' for s in signals); unk=sum(s.severity=='unknown' for s in signals)
    return '\n'.join([_card('card-total','Signals','Signale',total,'ok' if total else 'unknown'),_card('card-ok','OK','OK',ok,'ok'),_card('card-warn','Review','Prüfen',warn,'warn' if warn else 'ok'),_card('card-critical','Critical','Kritisch',crit,'critical' if crit else 'ok'),_card('card-unknown','Unknown','Unbekannt',unk,'unknown' if unk else 'ok')])

def _table(signals):
    rows=''.join(f"<tr><td><strong>{s.name}</strong></td><td>{s.area}</td><td><code>{html.escape(s.value)}</code></td><td>{s.state}</td><td><span class='sev-badge sev-{s.severity}'>{s.severity.upper()}</span></td><td>{s.note}</td></tr>" for s in signals)
    return f"<section class='health-panel'><div class='health-head'><h2>{l10n_text('Security Signals','Sicherheitssignale')}</h2><span class='pill'>{l10n_text('Cross-platform read-only review','Plattformübergreifende Nur-Lese-Prüfung')}</span></div><section class='messages'><p><strong>{l10n_text('Plain meaning','Einfache Bedeutung')}</strong>: {l10n_text('Security Pulse shows local orientation hints. It does not prove a problem and does not change the system.','Security Pulse zeigt lokale Orientierungshinweise. Es beweist kein Problem und ändert nichts am System.')}</p></section><section class='table-shell'><table><thead><tr><th>{l10n_text('Signal','Signal')}</th><th>{l10n_text('Area','Bereich')}</th><th>{l10n_text('Value','Wert')}</th><th>{l10n_text('State','Zustand')}</th><th>{l10n_text('Severity','Status')}</th><th>{l10n_text('Plain-English help','Einfache Erklärung')}</th></tr></thead><tbody>{rows}</tbody></table></section></section>"

def _render(template_path,output_path,generated,previous,config,signals):
    overall=_overall(signals); text=Path(template_path).read_text(encoding='utf-8')
    rec=l10n_text('Cross-platform local security orientation was collected where available. No settings were changed.','Plattformübergreifende lokale Sicherheitsorientierung wurde gesammelt, soweit verfügbar. Es wurden keine Einstellungen geändert.')
    for k,v in {"{{TITLE}}":"SECURITY PULSE","{{REFRESH_SECONDS}}":str(int(config.get('refresh_seconds',60))),"{{GENERATED_AT}}":html.escape(generated),"{{LAST_SUCCESS_AT}}":html.escape(previous),"{{OVERALL}}":overall.upper(),"{{OVERALL_CLASS}}":overall,"{{RECOMMENDATION}}":rec,"{{SUMMARY_CARDS}}":_cards(signals),"{{SECURITY_TABLE}}":_table(signals),"{{MESSAGES}}":f"<p>{l10n_text('No security refresh warnings.','Keine Sicherheits-Aktualisierungswarnungen.')}</p>"}.items(): text=text.replace(k,v)
    Path(output_path).write_text(text,encoding='utf-8')

def generate_security_pulse(output_path='security.html',template_path='security_template.html',config_path=None,state_path='.security_pulse_state.json'):
    if os_family()=='linux': return generate_linux_security_pulse(output_path=output_path,template_path=template_path,config_path=config_path,state_path=state_path)
    generated=_now(); previous=_last(state_path); config=_cfg(config_path)
    try:
        signals=_collect(config); _render(template_path,output_path,generated,previous,config,signals); _save(state_path,generated); return True
    except Exception:
        _render(template_path,output_path,generated,previous,config,[]); return False
