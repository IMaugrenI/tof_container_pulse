from ports_xplat import _classify, _dedupe, _entry, _parse_netstat, _split


def test_split_parses_ipv4_and_ipv6_ports():
    assert _split("127.0.0.1:8080") == ("127.0.0.1", "8080")
    assert _split("[::1]:443") == ("::1", "443")
    assert _split("*:80") == ("*", "80")


def test_classify_local_and_exposed_binds():
    assert _classify("127.0.0.1")[:2] == ("local-only", "ok")
    assert _classify("::1")[:2] == ("local-only", "ok")
    assert _classify("0.0.0.0")[:2] == ("all interfaces", "warn")
    assert _classify("192.168.1.10")[:2] == ("LAN/mesh", "warn")


def test_entry_adds_known_port_hint_and_severity():
    entry = _entry("tcp", "LISTEN", "127.0.0.1:5432")
    assert entry.proto == "tcp"
    assert entry.bind == "127.0.0.1"
    assert entry.port == "5432"
    assert entry.exposure == "local-only"
    assert entry.severity == "ok"
    assert "PostgreSQL" in entry.note


def test_parse_netstat_keeps_only_listeners():
    sample = """
Proto Recv-Q Send-Q Local Address           Foreign Address         State
Tcp      0      0 127.0.0.1:8080          0.0.0.0:0              LISTENING
TCP      0      0 192.168.1.2:22          0.0.0.0:0              ESTABLISHED
UDP      0      0 0.0.0.0:5353           *:*
"""
    entries = _parse_netstat(sample)
    assert len(entries) == 2
    assert {entry.port for entry in entries} == {"8080", "5353"}


def test_dedupe_removes_duplicate_listener_rows():
    first = _entry("tcp", "LISTEN", "127.0.0.1:8080")
    second = _entry("tcp", "LISTEN", "127.0.0.1:8080")
    assert _dedupe([first, second]) == [first]
