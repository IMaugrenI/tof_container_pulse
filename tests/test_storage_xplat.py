from storage_xplat import DEFAULT_CONFIG, Volume, _fmt_bytes, _fmt_pct, _level, _overall, _pct


def test_storage_percent_handles_boundaries():
    assert _pct(50, 100) == 50.0
    assert _pct(150, 100) == 100.0
    assert _pct(-10, 100) == 0.0
    assert _pct(None, 100) is None
    assert _pct(10, 0) is None


def test_storage_level_uses_warn_and_critical_thresholds():
    config = dict(DEFAULT_CONFIG)
    assert _level(None, config) == "unknown"
    assert _level(10.0, config) == "ok"
    assert _level(80.0, config) == "warn"
    assert _level(95.0, config) == "critical"


def test_storage_formatters_are_stable():
    assert _fmt_bytes(1024**3) == "1.0 GiB"
    assert _fmt_bytes(None) == "-"
    assert _fmt_pct(42.123) == "42.1%"
    assert _fmt_pct(None) == "-"


def test_storage_overall_picks_highest_severity():
    vols = [
        Volume("/", "root", "ext4", 100, 10, 90, 10.0, "ok", ""),
        Volume("/full", "full", "ext4", 100, 95, 5, 95.0, "critical", ""),
        Volume("/warn", "warn", "ext4", 100, 82, 18, 82.0, "warn", ""),
    ]
    assert _overall(vols) == "critical"
    assert _overall([]) == "unknown"
