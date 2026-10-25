from pulse_drift import detect_drift, normalize_ports, render_drift
from pulse_history import record_snapshot, load_history

def item(identity="id", image="app:v1", ports="8080->80/tcp", host="local"):
    return {"host":host,"container_id":identity,"name":"api","image":image,
            "state":"running","severity":"ok","ports":ports,
            "compose_project":"p","compose_service":"api"}

def test_safe_ports():
    assert normalize_ports("127.0.0.1:8080->80/tcp, [::]:8080->80/tcp, 443/tcp") == "443/tcp,8080->80/tcp"
    assert normalize_ports("password=secret") == ""

def test_image_and_port_drift_after_recreation(tmp_path):
    f=tmp_path/"hist.json"
    record_snapshot(f,["local"],[item()],at="2026-10-25T10:00:00+00:00")
    record_snapshot(f,["local"],[item("new","app:v2","8443->443/tcp")],at="2026-10-25T10:01:00+00:00")
    result=detect_drift(load_history(f))
    assert len(result)==1 and set(result[0]["fields"])=={"image","ports","recreated"}
    assert "8443-&gt;443/tcp" in render_drift(load_history(f))

def test_unknown_host_does_not_infer_drift(tmp_path):
    f=tmp_path/"hist.json"
    record_snapshot(f,["local"],[item()])
    record_snapshot(f,["remote"],[item(host="remote")])
    assert detect_drift(load_history(f))==[]

def test_old_snapshots_without_port_do_not_trigger_false_change(tmp_path):
    f=tmp_path/"hist.json"
    row=item()
    del row["ports"]
    record_snapshot(f,["local"],[row])
    record_snapshot(f,["local"],[item()])
    assert detect_drift(load_history(f))==[]

def test_ambiguous_recreation_not_inferred():
    old=[item("a"),item("b")]
    new=[item("c",image="new"),item("d",image="new")]
    snaps=[{"hosts":["local"],"containers":old,"at":"t1"},
           {"hosts":["local"],"containers":new,"at":"t2"}]
    assert detect_drift(snaps)==[]

def test_html_escapes_images(tmp_path):
    f=tmp_path/"hist.json"
    record_snapshot(f,["local"],[item()])
    record_snapshot(f,["local"],[item(image="<script>")])
    output=render_drift(load_history(f))
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
