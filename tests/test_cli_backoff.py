from cli.monitor import get_agent_fingerprint


def test_fingerprint_stability_with_order():
    data1 = [
        {
            "instance_id": "i1",
            "agent_id": "a1",
            "status": "idle",
            "reported_at": "2023-01-01T00:00:00Z",
        },
        {
            "instance_id": "i2",
            "agent_id": "a2",
            "status": "busy",
            "reported_at": "2023-01-01T00:00:01Z",
        },
    ]
    data2 = [
        {
            "instance_id": "i2",
            "agent_id": "a2",
            "status": "busy",
            "reported_at": "2023-01-01T00:00:01Z",
        },
        {
            "instance_id": "i1",
            "agent_id": "a1",
            "status": "idle",
            "reported_at": "2023-01-01T00:00:00Z",
        },
    ]

    assert get_agent_fingerprint(data1) == get_agent_fingerprint(data2)


def test_fingerprint_detects_instance_aware_changes():
    # Same agent_id, different branch
    data1 = [
        {"instance_id": "i1", "agent_id": "a1", "branch": "main", "status": "idle"}
    ]
    data2 = [
        {"instance_id": "i1", "agent_id": "a1", "branch": "feat", "status": "idle"}
    ]
    assert get_agent_fingerprint(data1) != get_agent_fingerprint(data2)

    # Same agent_id, different working_dir
    data3 = [
        {
            "instance_id": "i1",
            "agent_id": "a1",
            "working_dir": "/path/1",
            "status": "idle",
        }
    ]
    data4 = [
        {
            "instance_id": "i1",
            "agent_id": "a1",
            "working_dir": "/path/2",
            "status": "idle",
        }
    ]
    assert get_agent_fingerprint(data3) != get_agent_fingerprint(data4)


def test_fingerprint_ignores_volatile_fields():
    data1 = [
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T00:00:00Z"}
    ]
    data2 = [
        {"agent_id": "a1", "status": "idle", "reported_at": "2023-01-01T23:59:59Z"}
    ]

    assert get_agent_fingerprint(data1) == get_agent_fingerprint(data2)


def test_fingerprint_detects_semantic_changes():
    data1 = [{"agent_id": "a1", "status": "idle", "progress": 0}]
    data2 = [{"agent_id": "a1", "status": "busy", "progress": 10}]

    assert get_agent_fingerprint(data1) != get_agent_fingerprint(data2)


def test_fingerprint_handles_non_list_input():
    # Should be stable for strings/errors
    assert get_agent_fingerprint("Error") == get_agent_fingerprint("Error")
    assert get_agent_fingerprint("Error 1") != get_agent_fingerprint("Error 2")
