"""A local Ollama model is optional and never used by normal refresh paths."""
import json
import sys
from unittest.mock import patch

import pytest

import run
from pulse_explain import (
    ENDPOINT,
    MAX_RESPONSE_BYTES,
    _BlockRedirects,
    explain_incidents_locally,
    sanitized_explanation_context,
)
from pulse_history import record_snapshot
from pulse_reports import build_report


def stored_incident(tmp_path):
    path = tmp_path / "history.json"
    record_snapshot(path, ["private-host-42"], [{
        "host": "private-host-42", "container_id": "secret-id",
        "name": "secret-database", "image": "private/image:v2",
        "state": "running", "severity": "warn",
        "cpu_percent": 82, "memory_mb": 500, "memory_percent": 70,
    }])
    return path


def test_report_context_copies_only_anonymized_whitelisted_fields(tmp_path):
    report = build_report(stored_incident(tmp_path))
    context = sanitized_explanation_context(report)
    body = json.dumps(context)
    assert "host-1" in body
    for forbidden in ("private-host-42", "secret-id", "secret-database", "private/image"):
        assert forbidden not in body
    assert "incident" in body
    assert "containers" in body


def test_invalid_names_and_absent_history_prevent_any_network_call(tmp_path):
    for model in ("../../", "model;ping", "", "a" * 81):
        with patch("pulse_explain.urllib.request.build_opener") as opener:
            with pytest.raises(ValueError):
                explain_incidents_locally(str(stored_incident(tmp_path)), model)
            opener.assert_not_called()
    with patch("pulse_explain.urllib.request.build_opener") as opener:
        with pytest.raises(ValueError, match="No opted-in incident history"):
            explain_incidents_locally(str(tmp_path / "missing.json"), "local:3b")
        opener.assert_not_called()


def test_manual_ollama_request_is_loopback_only_capped_and_no_tools(tmp_path):
    captured = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def getcode(self):
            return 200
        def read(self, size):
            assert size == MAX_RESPONSE_BYTES + 1
            return json.dumps({"response": "Possible resource pressure. Manually check measurements."}).encode()

    class Opener:
        def open(self, request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return Response()

    with patch("pulse_explain.urllib.request.build_opener", return_value=Opener()) as factory:
        result = explain_incidents_locally(str(stored_incident(tmp_path)), "local:3b")
    assert captured["url"] == ENDPOINT == "http://127.0.0.1:11434/api/generate"
    assert captured["timeout"] == 15
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["keep_alive"] == "0s"
    assert captured["payload"]["options"]["num_predict"] == 256
    assert "tools" not in captured["payload"]
    assert "secret-database" not in captured["payload"]["prompt"]
    assert "ungeprüfte Erklärung" in result
    assert any(isinstance(arg, _BlockRedirects) for arg in factory.call_args.args)


def test_unbounded_model_response_is_rejected(tmp_path):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def getcode(self):
            return 200
        def read(self, size):
            return b"x" * size
    class Opener:
        def open(self, *args, **kwargs):
            return Response()
    with patch("pulse_explain.urllib.request.build_opener", return_value=Opener()):
        with pytest.raises(ValueError, match="size limit"):
            explain_incidents_locally(str(stored_incident(tmp_path)), "local")


def test_explicit_double_optin_is_required_before_llm_request(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run.py", "--explain-incidents", "--explain-model", "local"])
    with patch("run._load_config", return_value={"history_enabled": True,
                                                   "local_explanation_enabled": False}), \
         patch("run.explain_incidents_locally") as explain:
        with pytest.raises(SystemExit):
            run.main()
        explain.assert_not_called()


def test_automatic_suite_does_not_expose_llm_network_paths():
    import inspect
    assert "pulse_explain" not in inspect.getsource(run.generate_suite)
    assert "explain_incidents_locally" not in inspect.getsource(run.generate_suite)
