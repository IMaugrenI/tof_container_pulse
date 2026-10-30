"""Explicit, bounded loopback-only Ollama explanation for anonymized Pulse incidents.

No background request, Docker access, host commands, tools, cloud fallback,
model download, persistence, or implicit network use. Only manual CLI invocation.
"""
from __future__ import annotations

import json
import re
import urllib.request

from pulse_reports import build_report

ENDPOINT = "http://127.0.0.1:11434/api/generate"
MAX_REQUEST_BYTES = 14000
MAX_RESPONSE_BYTES = 32768
MAX_REPLY_CHARS = 4000
MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,79}\Z")


class _BlockRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _int_bounded(value: object, upper: int = 1000000) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(number, upper))


def sanitized_explanation_context(report: dict) -> dict:
    """Copy only known, non-identifying fields of the already anonymized report."""
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("Unsupported incident report schema")
    hosts = []
    aliases = set()
    for item in report.get("hosts", [])[:8]:
        alias = str(item.get("host_alias", ""))
        if not re.fullmatch(r"host-[1-9][0-9]{0,3}", alias):
            continue
        aliases.add(alias)
        levels = item.get("severity_counts") or {}
        hosts.append({
            "host": alias,
            "containers": _int_bounded(item.get("containers")),
            "open_incidents": _int_bounded(item.get("open_incidents")),
            "states": {name: _int_bounded(levels.get(name)) for name in ("ok", "warn", "critical", "unknown")},
            "high_cpu": _int_bounded(item.get("high_cpu_containers")),
            "high_memory": _int_bounded(item.get("high_memory_containers")),
            "unusual_cpu": _int_bounded(item.get("unusual_cpu_containers")),
            "unusual_memory": _int_bounded(item.get("unusual_memory_containers")),
        })
    permitted_reasons = {"unhealthy_container", "disappeared_from_listing", "unspecified"}
    incidents = []
    for item in report.get("incidents", [])[-20:]:
        if item.get("host_alias") not in aliases:
            continue
        severity = str(item.get("peak_severity", "unknown"))
        reason = str(item.get("reason", "unspecified"))
        incidents.append({
            "host": item["host_alias"],
            "severity": severity if severity in ("ok", "warn", "critical", "unknown") else "unknown",
            "reason": reason if reason in permitted_reasons else "unspecified",
            "resolved": bool(item.get("resolved_at")),
            "acknowledged": bool(item.get("acknowledged")),
        })
    return {"observations": _int_bounded(report.get("observations"), upper=240),
            "hosts": hosts, "incidents": incidents,
            "interpretation": "Aggregated read-only observations; no root-cause proof"}


def explain_incidents_locally(history_path: str, model: str, timeout_seconds: float = 15) -> str:
    """Manually request a tentative explanation from an existing local Ollama instance."""
    if not isinstance(model, str) or not MODEL_NAME.fullmatch(model):
        raise ValueError("A valid local model name is required")
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("Explanation timeout must be 1-30 seconds")

    context = sanitized_explanation_context(build_report(history_path))
    if context["observations"] == 0:
        raise ValueError("No opted-in incident history is available")

    prompt = (
        "You are a read-only assistant for a local infrastructure observer. "
        "The following is a minimal, anonymized set of observations, NOT a health or root-cause verdict. "
        "Write no more than five short sentences in German. Separate established observations from possible explanations. "
        "Suggest only manual verification, no commands, changes, service restarts, port changes, or automatic remediation. "
        "If evidence is insufficient, say so. Do not infer causality or identify any real host or user.\n\n"
        + json.dumps(context, ensure_ascii=True, separators=(",", ":"))
    )
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "keep_alive": "0s",
        "options": {"num_predict": 256, "num_ctx": 2048},
    }, ensure_ascii=True).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Local explanation context exceeds request limit")

    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"},
        method="POST",
    )
    # Ignore environment HTTP proxies and never follow redirects to any other endpoint.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _BlockRedirects())
    with opener.open(request, timeout=timeout_seconds) as response:
        if response.getcode() != 200:
            raise ValueError("Local explanation service did not return HTTP 200")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Local model response exceeds size limit")
    data = json.loads(raw.decode("utf-8"))
    answer = data.get("response", "") if isinstance(data, dict) else ""
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Local model returned no explanation")
    # Strip control codes so a model cannot inject terminal instructions.
    filtered = "".join(
        c for c in answer
        if c in "\n\t" or (ord(c) >= 32 and not 0x7F <= ord(c) <= 0x9F)
    )
    return "Hinweis: automatisch erzeugte, ungeprüfte Erklärung – keine Ursachenfeststellung.\n" + filtered.strip()[:MAX_REPLY_CHARS]
