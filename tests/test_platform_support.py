from platform_support import bytes_to_gib, percent, parse_float, parse_int


def test_parse_float_accepts_commas_and_strings():
    assert parse_float("12.5") == 12.5
    assert parse_float("12,5") == 12.5
    assert parse_float(None) is None
    assert parse_float("not-a-number") is None


def test_parse_int_accepts_float_like_strings():
    assert parse_int("12") == 12
    assert parse_int("12.0") == 12
    assert parse_int(None) is None
    assert parse_int("not-a-number") is None


def test_percent_clamps_and_handles_invalid_values():
    assert percent(50, 100) == 50.0
    assert percent(150, 100) == 100.0
    assert percent(-10, 100) == 0.0
    assert percent(1, 0) is None
    assert percent(None, 100) is None


def test_bytes_to_gib_formats_values():
    assert bytes_to_gib(1024**3) == "1.0 GiB"
    assert bytes_to_gib(None) == "-"
