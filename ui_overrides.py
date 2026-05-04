"""Small static UI post-processing helpers.

These helpers only adjust generated HTML presentation.
They do not collect system data, call Docker, inspect hardware, or perform
host actions.
"""

from pathlib import Path

SOFT_LIGHT_STYLE_ID = "tof-soft-light-mode-overrides"

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


def apply_soft_light_mode_overrides(output_path: str) -> None:
    """Inject softer light-mode CSS into a generated static HTML file."""

    path = Path(output_path)
    if not path.exists():
        return

    html = path.read_text(encoding="utf-8")
    if SOFT_LIGHT_STYLE_ID in html:
        return

    marker = "</head>"
    if marker not in html:
        return

    html = html.replace(marker, f"  {SOFT_LIGHT_STYLE}\n{marker}", 1)
    path.write_text(html, encoding="utf-8")
