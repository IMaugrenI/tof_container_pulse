from __future__ import annotations

import json

from pulse_capacity import capacity_rows, memory_projection, render_capacity
from pulse_history import record_snapshot, load_history
from pulse_notices import refresh_notices, render_notices


def sample(name="app", severity="ok", memory=120, host="local"):
    return {"host":host, "container_id":name, "name":name, "image":"app:v1",
            "state":"running", "severity":severity, "memory_mb":memory,
            "cpu_percent":20, "memory_percent":22}


def test_memory_projection_requires_positive_sustained_history():
    stamps=[f"2026-10-25T12:{i*5:02d}:00+00:00" for i in range(6)]
    growth=list(zip(stamps,[100,130,160,190,220,250]))
    eta=memory_projection(growth, 400)
    assert eta is not None and 0 < eta < 150
    assert memory_projection(growth[:4], 400) is None
    assert memory_projection(list(zip(stamps,[100,None,None,80,80,80])),400) is None
    assert memory_projection(list(zip(stamps,[100]*6)),400) is None


def test_host_summary_uses_last_success_per_host(tmp_path):
    path=tmp_path/"pulse.json"
    record_snapshot(path,["local"],[sample(memory=100)],at="2026-10-25T12:00:00+00:00")
    record_snapshot(path,["remote"],[sample(host="remote",severity="critical")],
                    at="2026-10-25T12:05:00+00:00")
    report=capacity_rows(load_history(path))
    assert len(report["hosts"])==2
    assert report["hosts"][0]["host"]=="local"
    assert report["hosts"][1]["critical"]==1
    assert "capacity overview" in render_capacity(load_history(path))


def test_notice_baseline_new_and_resolved_without_repeats(tmp_path):
    path=tmp_path/"notice.json"
    first=[{"id":"INC-alpha","peak_severity":"warn","resolved_at":None}]
    assert refresh_notices(path, first, "2026-10-25T12:00:00+00:00")==[]
    assert refresh_notices(path, first, "2026-10-25T12:05:00+00:00")==[]
    changed=first+[{"id":"INC-beta","peak_severity":"critical","resolved_at":None}]
    out=refresh_notices(path, changed, "2026-10-25T12:10:00+00:00")
    assert len(out)==1 and out[0]["state"]=="opened"
    changed[-1]["resolved_at"]="2026-10-25T12:15:00+00:00"
    out=refresh_notices(path, changed, "2026-10-25T12:15:00+00:00")
    assert len(out)==2 and out[-1]["state"]=="resolved"
    assert len(refresh_notices(path, changed))==2
    assert "notification inbox" in render_notices(out)
    assert json.loads(path.read_text())["version"]==1


def test_corrupted_notice_store_blocks_write(tmp_path):
    import pytest
    path=tmp_path/"notices.json"
    path.write_text("{invalid",encoding="utf-8")
    with pytest.raises(ValueError):
        refresh_notices(path,[])
    assert path.read_text()=="{invalid"
