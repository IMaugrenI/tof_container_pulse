from pulse_topology import compose_labels, render_diagnostics, render_topology, topology_data


def row(host, service, depends="", severity="ok", name=None):
    labels = compose_labels(
        "custom.label=ignored,com.docker.compose.project=stack,"
        f"com.docker.compose.service={service},com.docker.compose.depends_on={depends}"
    )
    return {"host": host, "name": name or service, "state": "running",
            "severity": severity, "labels": labels}


def test_only_explicit_dependency_edges_and_host_scoping():
    report = topology_data([
        row("server1", "api", "db:service_started:false"),
        row("server1", "db"),
        row("server2", "api"),
    ])
    assert len(report["projects"]) == 2
    server1 = next(p for p in report["projects"] if p["host"] == "server1")
    server2 = next(p for p in report["projects"] if p["host"] == "server2")
    assert server1["edges"] == [{"from": "api", "to": "db", "present": True}]
    assert server2["edges"] == []


def test_unseen_dependency_is_not_reported_as_confirmed():
    group = topology_data([row("host", "api", "db:service_started:false")])["projects"][0]
    assert group["edges"] == [{"from": "api", "to": "db", "present": False}]


def test_without_labels_does_not_infer_relationship():
    data = topology_data([{"host": "h", "name": "c", "severity": "unknown", "labels": ""}])
    assert data["projects"] == []
    assert data["standalone"] == 1


def test_escapes_untrusted_container_and_project_fields():
    evil = row("host<script>", "api")
    evil["labels"]["project"] = "<img onerror=1>"
    evil["name"] = "<script>"
    out = render_topology([evil]) + render_diagnostics([{
        "host": "host<script>", "name": "<img>", "severity": "critical"
    }])
    assert "<script>" not in out
    assert "<img onerror" not in out
    assert "&lt;script&gt;" in out


def test_label_parser_discards_unrelated_values():
    result = compose_labels("DB_PASSWORD=secret,com.docker.compose.project=x,com.docker.compose.service=api")
    assert result["project"] == "x"
    assert result["service"] == "api"
    assert "secret" not in str(result)


def test_unknown_and_failed_host_have_non_autonomous_guidance():
    out = render_diagnostics([{"host": "h", "name": "api", "severity": "unknown"}], ["remote"])
    assert "remote" in out
    assert "metrics unavailable" in out
    assert "restart" not in out.lower()
