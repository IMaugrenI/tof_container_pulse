from pulse_suite_overview import add_suite_summary, collection_summary


def test_six_page_statuses_never_become_health_claims():
    html = collection_summary({
        "containers": True, "hardware": False, "ports": None,
        "storage": True, "services": True, "security": True,
    })
    assert "4 of 6 collectors completed" in html
    assert "Collection status is not system health" in html
    assert "Erfassung fehlgeschlagen" in html
    assert html.count("<tr>") == 6


def test_suite_injection_is_idempotent_and_changes_only_generated_html(tmp_path):
    path = tmp_path / "pulse.html"
    path.write_text('<main><section class="feature-strip" aria-label="Design principles"></section></main>')
    results = {page: True for page in
               ("containers","hardware","ports","storage","services","security")}
    assert add_suite_summary(path, results) is True
    before = path.read_bytes()
    assert b"pulse-suite-summary" in before
    assert add_suite_summary(path, results) is False
    assert path.read_bytes() == before


def test_missing_output_does_not_create_another_page(tmp_path):
    target = tmp_path / "missing.html"
    assert add_suite_summary(target, {}) is False
    assert not target.exists()
