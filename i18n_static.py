"""Tiny helpers for bilingual generated static HTML fragments.

The page templates already translate many fixed labels with data-i18n keys.
Generated rows, recommendations, summaries, and notes need a different path
because they are created by Python at render time. These helpers keep those
fragments safe and language-switchable without introducing a frontend build
step or runtime dependency.
"""

from __future__ import annotations

import html


def l10n_text(en: str, de: str) -> str:
    """Return a safe inline span that can switch between English and German."""

    safe_en = html.escape(str(en), quote=True)
    safe_de = html.escape(str(de), quote=True)
    return f'<span data-l10n-en="{safe_en}" data-l10n-de="{safe_de}">{safe_en}</span>'


def l10n_title(en: str, de: str) -> str:
    """Return data attributes for translated title/tool-tip text."""

    safe_en = html.escape(str(en), quote=True)
    safe_de = html.escape(str(de), quote=True)
    return f'data-l10n-title-en="{safe_en}" data-l10n-title-de="{safe_de}" title="{safe_en}"'
