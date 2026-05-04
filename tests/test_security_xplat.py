from security_xplat import Signal, _overall, _sig


def test_security_sig_builds_translated_signal_shape():
    signal = _sig(
        "Docker visibility",
        "Docker-Sichtbarkeit",
        "Containers",
        "Container",
        3,
        "present",
        "ok",
        "Docker responded.",
        "Docker hat geantwortet.",
    )
    assert signal.name
    assert signal.area
    assert signal.value == "3"
    assert signal.severity == "ok"
    assert signal.note


def test_security_overall_picks_highest_severity():
    signals = [
        Signal("ok", "area", "value", "state", "ok", "note"),
        Signal("warn", "area", "value", "state", "warn", "note"),
        Signal("unknown", "area", "value", "state", "unknown", "note"),
    ]
    assert _overall(signals) == "warn"
    assert _overall([]) == "unknown"
