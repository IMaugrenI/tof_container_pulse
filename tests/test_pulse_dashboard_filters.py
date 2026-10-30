"""Static dashboard filter contract; no browser automation required during build."""
from pathlib import Path


def test_existing_container_table_has_view_only_host_and_severity_filters():
    source = Path("template.html").read_text(encoding="utf-8")
    assert 'id="pulse-container-rows"' in source
    assert 'id="pulse-filter-host"' in source
    assert 'id="pulse-filter-severity"' in source
    assert 'id="pulse-filter-count"' in source
    assert "row.cells[0].textContent.trim()" in source
    assert "row.cells[2].textContent.trim().toLowerCase()" in source
    assert "row.style.display = selected ? '' : 'none'" in source
    assert "hostInput.addEventListener('change', update)" in source
    assert "severityInput.addEventListener('change', update)" in source
    assert 'data-l10n-de="Alle Hosts"' in source
    assert "{{ROWS}}" in source
