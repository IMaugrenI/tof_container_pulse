"""Small static UI post-processing helpers.

These helpers only adjust generated HTML presentation and generated-text
language switching. They do not collect system data, call Docker, inspect
hardware, scan ports, or perform host actions.
"""

import html
from pathlib import Path

from platform_support import os_family, platform_label

SOFT_LIGHT_STYLE_ID = "tof-soft-light-mode-overrides"
GENERATED_L10N_SCRIPT_ID = "tof-generated-l10n-overrides"
CONTAINER_NAV_MARKER = "tof-container-suite-navigation"
PLATFORM_BADGE_STYLE_ID = "tof-platform-badge-overrides"
PLATFORM_BADGE_MARKER = "tof-platform-badges"

SOFT_LIGHT_STYLE = f"""
<style id=\"{SOFT_LIGHT_STYLE_ID}\">
  body.light {{
    --bg-0: #d7e4ef;
    --bg-1: #c8d8e7;
    --bg-2: #edf4f8;
    --panel: rgba(239, 246, 250, 0.88);
    --panel-soft: rgba(229, 239, 246, 0.78);
    --panel-softer: rgba(221, 234, 242, 0.82);
    --panel-line: rgba(54, 86, 111, 0.22);
    --text: #172435;
    --text-strong: #0b1522;
    --code-text: #18314a;
    --muted: #53677c;
    --muted-2: #718294;
    --teal: #0f766e;
    --cyan: #0b6b8f;
    --shadow: rgba(15, 23, 42, 0.18);
    --grid-line: rgba(54, 86, 111, 0.055);
    --hero-line-a: rgba(54, 86, 111, 0.18);
    --hero-line-b: rgba(37, 99, 235, 0.10);
    --glow-a: rgba(20, 184, 166, 0.13);
    --glow-b: rgba(37, 99, 235, 0.10);
    --glow-c: rgba(20, 184, 166, 0.08);
  }}

  body.light .pulse-word {{
    color: #0f766e;
    text-shadow: none;
  }}

  .nav-strip {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
  }}

  .nav-link {{
    appearance: none;
    border: 1px solid var(--panel-line);
    border-radius: 999px;
    padding: 7px 11px;
    min-height: 32px;
    color: var(--text);
    background: var(--panel-soft);
    box-shadow: inset 0 0 18px rgba(255,255,255,0.03);
    white-space: nowrap;
    font: inherit;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.02em;
    cursor: pointer;
    text-decoration: none;
    transition: border-color 140ms ease, transform 140ms ease, background 140ms ease;
  }}

  .nav-link:hover {{
    border-color: rgba(54, 243, 211, 0.42);
    transform: translateY(-1px);
  }}

  .nav-link.active {{
    border-color: rgba(54, 243, 211, 0.58);
    color: var(--teal);
  }}

  .nav-link.disabled {{
    cursor: default;
    opacity: 0.52;
  }}

  .nav-link.disabled:hover {{
    transform: none;
    border-color: var(--panel-line);
  }}

  body.light .panel,
  body.light .health-panel,
  body.light .messages,
  body.light .card,
  body.light .feature,
  body.light .pill,
  body.light .control-button,
  body.light .nav-link {{
    background-color: rgba(232, 241, 247, 0.78);
  }}

  body.light .table-shell,
  body.light .metric-row {{
    background: rgba(221, 234, 242, 0.76);
  }}
</style>
""".strip()

PLATFORM_BADGE_STYLE = f"""
<style id=\"{PLATFORM_BADGE_STYLE_ID}\">
  .platform-badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
    max-width: 720px;
  }}
  .platform-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 10px;
    border: 1px solid var(--panel-line);
    border-radius: 999px;
    background: var(--panel-soft);
    color: var(--muted);
    font-size: 11px;
    font-weight: 850;
    letter-spacing: 0.035em;
    text-transform: uppercase;
    white-space: nowrap;
  }}
  .platform-badge strong {{
    color: var(--text-strong);
    font-weight: 900;
    letter-spacing: 0.02em;
  }}
  .platform-badge-readonly strong {{ color: var(--teal); }}
  .platform-badge-deep strong {{ color: var(--green); }}
  .platform-badge-baseline strong {{ color: var(--yellow); }}
  body.light .platform-badge {{ background-color: rgba(232, 241, 247, 0.78); }}
  @media (max-width: 980px) {{
    .platform-badges {{ justify-content: flex-start; }}
  }}
</style>
""".strip()

GENERATED_L10N_SCRIPT = f"""
<script id=\"{GENERATED_L10N_SCRIPT_ID}\">
(function () {{
  function currentLang() {{
    return localStorage.getItem('tof_container_pulse_language') || document.documentElement.lang || 'en';
  }}

  function applyGeneratedLanguage() {{
    var lang = currentLang() === 'de' ? 'de' : 'en';
    document.querySelectorAll('[data-l10n-en][data-l10n-de]').forEach(function (element) {{
      element.textContent = lang === 'de' ? element.dataset.l10nDe : element.dataset.l10nEn;
    }});
    document.querySelectorAll('[data-l10n-title-en][data-l10n-title-de]').forEach(function (element) {{
      element.setAttribute('title', lang === 'de' ? element.dataset.l10nTitleDe : element.dataset.l10nTitleEn);
    }});
  }}

  var baseApplyLanguage = window.applyLanguage;
  window.applyLanguage = function () {{
    if (typeof baseApplyLanguage === 'function') {{
      baseApplyLanguage();
    }}
    applyGeneratedLanguage();
  }};

  applyGeneratedLanguage();
}}());
</script>
""".strip()

CONTAINER_NAV_HTML = f"""
        <nav class=\"nav-strip\" id=\"{CONTAINER_NAV_MARKER}\" aria-label=\"Pulse Suite navigation\">
          <a class=\"nav-link active\" href=\"pulse.html\"><span data-l10n-en=\"Container\" data-l10n-de=\"Container\">Container</span></a>
          <a class=\"nav-link\" href=\"hardware.html\"><span data-l10n-en=\"Hardware\" data-l10n-de=\"Hardware\">Hardware</span></a>
          <a class=\"nav-link\" href=\"ports.html\"><span data-l10n-en=\"Ports\" data-l10n-de=\"Ports\">Ports</span></a>
          <a class=\"nav-link\" href=\"storage.html\"><span data-l10n-en=\"Storage\" data-l10n-de=\"Speicher\">Storage</span></a>
          <a class=\"nav-link\" href=\"services.html\"><span data-l10n-en=\"Services\" data-l10n-de=\"Dienste\">Services</span></a>
          <a class=\"nav-link\" href=\"security.html\"><span data-l10n-en=\"Security\" data-l10n-de=\"Sicherheit\">Security</span></a>
        </nav>
""".rstrip()


def _collector_mode(page_key: str) -> tuple[str, str, str]:
    family = os_family()
    if page_key == "container":
        return "Docker CLI", "Docker CLI", "ok"
    if page_key == "services":
        return "Configured", "Konfiguriert", "ok"
    if page_key in {"hardware", "ports", "storage", "security"}:
        if family == "linux":
            return "Deep", "Tief", "deep"
        return "Baseline", "Basis", "baseline"
    return "Unknown", "Unbekannt", "unknown"


def _platform_badges_html(page_key: str) -> str:
    collector_en, collector_de, collector_kind = _collector_mode(page_key)
    platform_text = html.escape(platform_label())
    safe_collector_en = html.escape(collector_en)
    safe_collector_de = html.escape(collector_de)
    safe_collector_kind = html.escape(collector_kind)
    return f"""
        <div class=\"platform-badges\" id=\"{PLATFORM_BADGE_MARKER}\" aria-label=\"Platform and collector mode\">
          <span class=\"platform-badge\"><span data-l10n-en=\"Platform\" data-l10n-de=\"Plattform\">Platform</span>: <strong>{platform_text}</strong></span>
          <span class=\"platform-badge platform-badge-{safe_collector_kind}\"><span data-l10n-en=\"Collector\" data-l10n-de=\"Collector\">Collector</span>: <strong data-l10n-en=\"{safe_collector_en}\" data-l10n-de=\"{safe_collector_de}\">{safe_collector_en}</strong></span>
          <span class=\"platform-badge platform-badge-readonly\"><span data-l10n-en=\"Mode\" data-l10n-de=\"Modus\">Mode</span>: <strong data-l10n-en=\"Read-only\" data-l10n-de=\"Nur lesend\">Read-only</strong></span>
        </div>
""".rstrip()


def apply_soft_light_mode_overrides(output_path: str) -> None:
    """Inject softer light-mode CSS into a generated static HTML file."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    if SOFT_LIGHT_STYLE_ID not in html_text:
        marker = "</head>"
        if marker in html_text:
            html_text = html_text.replace(marker, f"  {SOFT_LIGHT_STYLE}\n{marker}", 1)

    path.write_text(html_text, encoding="utf-8")


def apply_platform_badges(output_path: str, page_key: str) -> None:
    """Inject platform, collector mode, and read-only badges into a page."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    if PLATFORM_BADGE_STYLE_ID not in html_text:
        marker = "</head>"
        if marker in html_text:
            html_text = html_text.replace(marker, f"  {PLATFORM_BADGE_STYLE}\n{marker}", 1)

    if PLATFORM_BADGE_MARKER not in html_text:
        nav_end = "        </nav>"
        if nav_end in html_text:
            html_text = html_text.replace(nav_end, f"{nav_end}\n{_platform_badges_html(page_key)}", 1)

    path.write_text(html_text, encoding="utf-8")


def apply_generated_l10n(output_path: str) -> None:
    """Enable language switching for Python-generated HTML fragments."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    if GENERATED_L10N_SCRIPT_ID in html_text:
        return

    marker = "</body>"
    if marker not in html_text:
        return

    html_text = html_text.replace(marker, f"  {GENERATED_L10N_SCRIPT}\n{marker}", 1)
    path.write_text(html_text, encoding="utf-8")


def apply_container_suite_navigation(output_path: str) -> None:
    """Add Pulse Suite navigation to generated Container Pulse output."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    if CONTAINER_NAV_MARKER in html_text:
        return

    anchor = '        <span class="pill"><span class="dot"></span> <span data-i18n="oneGlance">'
    if anchor not in html_text:
        return

    html_text = html_text.replace(anchor, f"{CONTAINER_NAV_HTML}\n{anchor}", 1)
    path.write_text(html_text, encoding="utf-8")


def apply_active_ports_navigation(output_path: str) -> None:
    """Make the Ports navigation item clickable on generated active pages."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navPorts">Ports</span>',
        '<a class="nav-link" href="ports.html" data-i18n="navPorts">Ports</a>',
    )
    path.write_text(html_text, encoding="utf-8")


def apply_active_storage_navigation(output_path: str) -> None:
    """Make the Storage navigation item clickable on generated active pages."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navStorage">Storage</span>',
        '<a class="nav-link" href="storage.html" data-i18n="navStorage">Storage</a>',
    )
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navStorage">Speicher</span>',
        '<a class="nav-link" href="storage.html" data-i18n="navStorage">Speicher</a>',
    )
    path.write_text(html_text, encoding="utf-8")


def apply_active_services_navigation(output_path: str) -> None:
    """Make the Services navigation item clickable on generated active pages."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navServices">Services</span>',
        '<a class="nav-link" href="services.html" data-i18n="navServices">Services</a>',
    )
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navServices">Dienste</span>',
        '<a class="nav-link" href="services.html" data-i18n="navServices">Dienste</a>',
    )
    path.write_text(html_text, encoding="utf-8")


def apply_active_security_navigation(output_path: str) -> None:
    """Make the Security navigation item clickable on generated active pages."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navSecurity">Security</span>',
        '<a class="nav-link" href="security.html" data-i18n="navSecurity">Security</a>',
    )
    html_text = html_text.replace(
        '<span class="nav-link disabled" data-i18n="navSecurity">Sicherheit</span>',
        '<a class="nav-link" href="security.html" data-i18n="navSecurity">Sicherheit</a>',
    )
    path.write_text(html_text, encoding="utf-8")
