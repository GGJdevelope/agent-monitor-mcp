import argparse
import json
import time
import requests
import hashlib
from tabulate import tabulate
from datetime import datetime


def fetch_status(api_url):
    try:
        response = requests.get(f"{api_url}/api/agents")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return f"Error fetching status: {e}"


def get_agent_fingerprint(data):
    """
    Generate a deterministic fingerprint for agent states.
    Ignores volatile fields like 'reported_at'.
    Sorts agents by instance_id to be stable even if API order changes.
    """
    if not isinstance(data, list):
        return str(data)

    # Sort agents by instance_id for stable fingerprinting
    sorted_agents = sorted(
        data, key=lambda x: str(x.get("instance_id", x.get("agent_id", "")))
    )

    # Select fields that represent "semantic" state changes
    fingerprint_data = []
    for agent in sorted_agents:
        fingerprint_data.append(
            {
                "instance_id": agent.get("instance_id"),
                "agent_id": agent.get("agent_id"),
                "branch": agent.get("branch"),
                "location_label": agent.get("location_label"),
                "working_dir": agent.get("working_dir"),
                "task_name": agent.get("task_name"),
                "status": agent.get("status"),
                "progress": agent.get("progress"),
                "message": agent.get("message"),
            }
        )

    return hashlib.md5(
        json.dumps(fingerprint_data, sort_keys=True).encode()
    ).hexdigest()


def format_table(data, limit=None):
    if not isinstance(data, list):
        return data

    # Copy data to avoid mutating caller state if we need to sort it
    display_data = list(data)
    total_agents = len(display_data)

    # Sort data by updated_at descending (newest first)
    # Default to reported_at if updated_at is missing, though API should provide it
    display_data.sort(
        key=lambda x: x.get("updated_at", x.get("reported_at", "")), reverse=True
    )

    if limit and limit > 0:
        display_data = display_data[:limit]

    table_data = []

    for agent in display_data:
        # Use location_label if available, otherwise fallback
        location = agent.get("location_label", "")
        if not location:
            working_dir = agent.get("working_dir")
            if working_dir:
                # Derive a compact label from the path to preserve privacy boundary
                parts = [p for p in working_dir.replace("\\", "/").split("/") if p]
                if len(parts) >= 2:
                    location = f"{parts[-2]}/{parts[-1]}"
                elif parts:
                    location = parts[-1]
                else:
                    location = "root"
            else:
                location = "unknown"

        row = [
            location,
            agent.get("branch", "-"),
            agent.get("status"),
            f"{agent.get('progress', 0)}%",
        ]

        table_data.append(row)

    headers = ["Location", "Branch", "Status", "Progress"]

    if not table_data:
        return "No active agents."

    output = tabulate(table_data, headers=headers, tablefmt="grid")
    if limit and total_agents > limit:
        output += f"\nShowing {limit} of {total_agents} agents (use --limit to see more)"
    return output


def main():
    parser = argparse.ArgumentParser(description="Agent Monitor CLI")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--once", action="store_true", help="Fetch status once and exit"
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Initial polling interval in seconds",
    )
    parser.add_argument(
        "--max-interval",
        type=float,
        default=60.0,
        help="Maximum polling interval for backoff",
    )
    parser.add_argument(
        "--backoff-factor",
        type=float,
        default=1.5,
        help="Backoff multiplier when no changes detected",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit the number of agents displayed (sorted by updated_at descending)",
    )

    args = parser.parse_args()

    if args.limit and args.limit < 0:
        parser.error("--limit must be a positive integer")

    current_interval = args.interval
    last_fingerprint = None

    try:
        while True:
            data = fetch_status(args.url)

            # Handle error/string responses
            if not isinstance(data, list):
                if args.json:
                    print(json.dumps({"error": data}))
                else:
                    print(data)
                if args.once:
                    break
                time.sleep(args.interval)
                continue

            current_fingerprint = get_agent_fingerprint(data)

            # Change detection and interval management
            if last_fingerprint is not None and current_fingerprint == last_fingerprint:
                # No change: increase interval
                current_interval = min(
                    current_interval * args.backoff_factor, args.max_interval
                )
            else:
                # Change detected or first fetch: reset interval
                current_interval = args.interval

            last_fingerprint = current_fingerprint

            if args.json:
                print(json.dumps(data, indent=2))
            else:
                if not args.once:
                    # Clear screen for watch mode
                    print("\033[H\033[J", end="")
                    print(
                        f"Agent Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    # Suppress noisy backoff lines in normal stable rendering unless there's an error
                    # We'll only show it if it's the very first backoff or if we want to be very calm.
                    # The requirement says "suppress noisy backoff lines in normal stable rendering"
                
                print(format_table(data, limit=args.limit))

            if args.once:
                break

            time.sleep(current_interval)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
