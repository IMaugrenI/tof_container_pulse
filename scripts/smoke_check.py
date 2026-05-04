"""Cross-platform smoke check for Pulse Suite.

This script intentionally performs only local read-only validation:

- compile all Python files
- generate the static Pulse Suite once
- verify that all expected HTML files exist and look rendered

It does not require Docker to be running and does not require sudo/admin rights.
"""

from __future__ import annotations

import compileall
import os
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_HTML = (
    "pulse.html",
    "hardware.html",
    "ports.html",
    "storage.html",
    "services.html",
    "security.html",
)

# Match the suite's real template placeholders, such as {{TITLE}}, {{ROWS}},
# {{OVERALL_CLASS}}, or {{REFRESH_SECONDS}}. Do not flag arbitrary braces like
# Docker format strings that may appear inside diagnostic text, for example
# {{json .}} on platforms where Docker returns command context in an error.
TEMPLATE_PLACEHOLDER_RE = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")


def fail(message: str) -> int:
    print(f"SMOKE_CHECK_FAIL: {message}", file=sys.stderr)
    return 1


def compile_python() -> bool:
    print("[smoke] compiling Python files")
    return compileall.compile_dir(".", quiet=1, force=True)


def generate_suite() -> subprocess.CompletedProcess[str]:
    print("[smoke] generating Pulse Suite once")
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.run(
        [sys.executable, "run.py", "--once", "--no-open"],
        text=True,
        capture_output=True,
        timeout=120,
        env=env,
        check=False,
    )


def validate_html_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing generated file: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"could not read {path}: {exc}"]
    if len(content) < 1000:
        errors.append(f"generated file too small: {path} ({len(content)} bytes)")
    lowered = content.lower()
    if "<!doctype html" not in lowered:
        errors.append(f"missing doctype: {path}")
    if "</html>" not in lowered:
        errors.append(f"missing closing html tag: {path}")
    match = TEMPLATE_PLACEHOLDER_RE.search(content)
    if match:
        errors.append(f"unrendered template placeholder found in {path}: {match.group(0)}")
    return errors


def validate_outputs() -> list[str]:
    print("[smoke] validating generated HTML outputs")
    errors: list[str] = []
    for name in EXPECTED_HTML:
        errors.extend(validate_html_file(Path(name)))
    return errors


def main() -> int:
    print(f"[smoke] Python: {sys.version}")
    print(f"[smoke] Platform: {sys.platform}")

    if not compile_python():
        return fail("Python compilation failed")

    result = generate_suite()
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        return fail(f"run.py exited with {result.returncode}")

    errors = validate_outputs()
    if errors:
        for error in errors:
            print(f"[smoke] {error}", file=sys.stderr)
        return fail("generated output validation failed")

    print("SMOKE_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
