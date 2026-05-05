"""Light-mode contrast polish for generated Pulse Suite pages."""

from pathlib import Path

LIGHT_PANEL_CONTRAST_STYLE_ID = "tof-light-panel-contrast-polish"

LIGHT_PANEL_CONTRAST_STYLE = f"""
<style id=\"{LIGHT_PANEL_CONTRAST_STYLE_ID}\">
  body.light {{
    --panel: rgba(231, 240, 246, 0.92);
    --panel-soft: rgba(220, 233, 242, 0.84);
    --panel-softer: rgba(211, 226, 237, 0.86);
    --panel-line: rgba(54, 86, 111, 0.24);
    --shadow: rgba(15, 23, 42, 0.20);
    --grid-line: rgba(54, 86, 111, 0.065);
    --hero-line-a: rgba(54, 86, 111, 0.20);
    --hero-line-b: rgba(37, 99, 235, 0.11);
  }}

  body.light .panel,
  body.light .health-panel,
  body.light .messages,
  body.light .card,
  body.light .feature,
  body.light .pill,
  body.light .control-button,
  body.light .nav-link,
  body.light .platform-badge {{
    background-color: rgba(224, 236, 244, 0.84);
  }}

  body.light .table-shell,
  body.light .metric-row {{
    background: rgba(211, 226, 237, 0.82);
  }}
</style>
""".strip()


def apply_light_panel_contrast(output_path: str) -> None:
    """Insert a tiny light-mode contrast override into a generated HTML file."""

    path = Path(output_path)
    if not path.exists():
        return

    html_text = path.read_text(encoding="utf-8")
    if LIGHT_PANEL_CONTRAST_STYLE_ID in html_text:
        return

    marker = "</head>"
    if marker not in html_text:
        return

    html_text = html_text.replace(marker, f"  {LIGHT_PANEL_CONTRAST_STYLE}\n{marker}", 1)
    path.write_text(html_text, encoding="utf-8")
