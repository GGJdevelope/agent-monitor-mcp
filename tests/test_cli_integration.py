import sys
import json
from unittest.mock import patch, MagicMock
from cli.monitor import main

def test_main_once_limit(capsys):
    """
    Test main function with --once and --limit arguments.
    Verifies that it fetches status once, applies limit, and exits.
    """
    mock_data = [
        {"location_label": "agent-1", "status": "running", "updated_at": "2026-03-21T12:00:00Z"},
        {"location_label": "agent-2", "status": "failed", "updated_at": "2026-03-21T11:00:00Z"},
        {"location_label": "agent-3", "status": "running", "updated_at": "2026-03-21T10:00:00Z"},
    ]

    # Mocking requests.get via fetch_status
    with patch("cli.monitor.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Mocking sys.argv
        test_args = ["monitor.py", "--once", "--limit", "2"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    output = captured.out

    # Verify limit was applied: only 2 agents shown
    assert "agent-1" in output
    assert "agent-2" in output
    assert "agent-3" not in output
    
    # Verify NO disclosure even if agent-2 (failed) was in the set
    assert "Task" not in output
    assert "Message" not in output
    
    # Verify limit footer
    assert "Showing 2 of 3 agents" in output
    
    # Verify no backoff line (since it's --once)
    assert "Polling interval" not in output

def test_main_once_json(capsys):
    """
    Test main function with --once and --json.
    """
    mock_data = [{"agent_id": "test", "status": "running"}]
    
    with patch("cli.monitor.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        test_args = ["monitor.py", "--once", "--json"]
        with patch.object(sys, "argv", test_args):
            main()

    captured = capsys.readouterr()
    output = captured.out
    
    # Verify valid JSON output
    data = json.loads(output)
    assert data[0]["agent_id"] == "test"

def test_format_table_no_disclosure_on_hidden_agent():
    """
    Test that disclosure is NOT triggered even if the agent causing it is hidden by --limit.
    """
    from cli.monitor import format_table
    data = [
        {"location_label": "visible", "status": "running", "updated_at": "2026-03-21T12:00:00Z"},
        {"location_label": "hidden", "status": "failed", "updated_at": "2026-03-21T11:00:00Z"},
    ]
    # Limit to 1, so "hidden" is not in display_data, but it's in the full set
    output = format_table(data, limit=1)
    
    assert "visible" in output
    assert "hidden" not in output
    assert "Task" not in output  # Should NOT be present anymore
    assert "Showing 1 of 2 agents" in output
