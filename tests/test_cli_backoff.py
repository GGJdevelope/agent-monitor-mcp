import pytest
from cli.monitor import get_agent_fingerprint

def test_fingerprint_stability_with_order():
    data1 = [
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T00:00:00Z"},
        {"agent_id": "a2", "status": "busy", "reported_at": "2023-01-01T00:00:01Z"}
    ]
    data2 = [
        {"agent_id": "a2", "status": "busy", "reported_at": "2023-01-01T00:00:01Z"},
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T00:00:00Z"}
    ]
    
    assert get_agent_fingerprint(data1) == get_agent_fingerprint(data2)

def test_fingerprint_ignores_volatile_fields():
    data1 = [
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T00:00:00Z"}
    ]
    data2 = [
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T23:59:59Z"}
    ]
    
    assert get_agent_fingerprint(data1) == get_agent_fingerprint(data2)

def test_fingerprint_detects_semantic_changes():
    data1 = [
        {"agent_id": "a1", "status": "idle", "progress": 0}
    ]
    data2 = [
        {"agent_id": "a1", "status": "busy", "progress": 10}
    ]
    
    assert get_agent_fingerprint(data1) != get_agent_fingerprint(data2)

def test_fingerprint_handles_non_list_input():
    # Should be stable for strings/errors
    assert get_agent_fingerprint("Error") == get_agent_fingerprint("Error")
    assert get_agent_fingerprint("Error 1") != get_agent_fingerprint("Error 2")
