from cli.monitor import format_table

def test_format_table_default_columns():
    data = [
        {
            "location_label": "project/dir",
            "branch": "main",
            "status": "running",
            "progress": 50,
            "task_name": "Task 1",
            "message": "Working...",
            "reported_at": "2026-03-21T12:00:00Z",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    output = format_table(data)
    assert "Location" in output
    assert "Branch" in output
    assert "Status" in output
    assert "Progress" in output
    assert "Task" not in output
    assert "Message" not in output
    assert "project/dir" in output
    assert "main" in output
    assert "running" in output
    assert "50%" in output

def test_format_table_no_disclosure_on_failed():
    data = [
        {
            "location_label": "project/dir",
            "branch": "main",
            "status": "failed",
            "progress": 10,
            "task_name": "Broken Task",
            "message": "Error occurred",
            "reported_at": "2026-03-21T12:00:00Z",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    output = format_table(data)
    # MUST only have 4 columns, even on failure
    assert "Location" in output
    assert "Branch" in output
    assert "Status" in output
    assert "Progress" in output
    assert "Task" not in output
    assert "Message" not in output
    assert "Time (UTC)" not in output
    assert "Broken Task" not in output
    assert "Error occurred" not in output

def test_format_table_no_disclosure_on_cancelled():
    data = [{"status": "cancelled", "location_label": "loc"}]
    output = format_table(data)
    assert "Task" not in output

def test_format_table_no_disclosure_on_queued():
    data = [{"status": "queued", "location_label": "loc"}]
    output = format_table(data)
    assert "Task" not in output

def test_format_table_no_disclosure_on_stale():
    data = [
        {
            "location_label": "project/dir",
            "branch": "main",
            "status": "stale",
            "progress": 50,
            "task_name": "Ghost Task",
            "message": "No response",
            "reported_at": "2026-03-21T11:00:00Z",
            "updated_at": "2026-03-21T11:00:00Z"
        }
    ]
    output = format_table(data)
    assert "Task" not in output
    assert "Ghost Task" not in output

def test_format_table_sorting():
    data = [
        {"location_label": "old", "updated_at": "2026-03-21T10:00:00Z", "status": "running"},
        {"location_label": "new", "updated_at": "2026-03-21T12:00:00Z", "status": "running"},
        {"location_label": "mid", "updated_at": "2026-03-21T11:00:00Z", "status": "running"},
    ]
    output = format_table(data)
    # Check order in table
    table_lines = [line for line in output.split("\n") if "running" in line]
    assert "new" in table_lines[0]
    assert "mid" in table_lines[1]
    assert "old" in table_lines[2]

def test_format_table_limit():
    data = [
        {"location_label": "item-1", "updated_at": "2026-03-21T12:00:00Z", "status": "running"},
        {"location_label": "item-2", "updated_at": "2026-03-21T11:00:00Z", "status": "running"},
        {"location_label": "item-3", "updated_at": "2026-03-21T10:00:00Z", "status": "running"},
    ]
    output = format_table(data, limit=2)
    assert "item-1" in output
    assert "item-2" in output
    assert "item-3" not in output
    assert "Showing 2 of 3 agents" in output

def test_format_table_privacy():
    data = [
        {
            "location_label": "my-project",
            "working_dir": "/Users/secret/path/to/my-project",
            "status": "running",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    output = format_table(data)
    assert "my-project" in output
    assert "/Users/secret" not in output

def test_format_table_empty():
    output = format_table([])
    assert "No active agents" in output

def test_format_table_fallback_location():
    data = [
        {
            "agent_id": "test-agent",
            "working_dir": "/path/to/my-dir",
            "status": "running",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    # No location_label provided, should derive 'to/my-dir'
    output = format_table(data)
    assert "to/my-dir" in output
    assert "/path/to" not in output

def test_format_table_fallback_location_root():
    data = [
        {
            "agent_id": "test-agent",
            "working_dir": "/",
            "status": "running",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    output = format_table(data)
    assert "root" in output

def test_format_table_fallback_location_single():
    data = [
        {
            "agent_id": "test-agent",
            "working_dir": "/my-dir",
            "status": "running",
            "updated_at": "2026-03-21T12:00:00Z"
        }
    ]
    output = format_table(data)
    assert "my-dir" in output
    assert "root/my-dir" not in output
