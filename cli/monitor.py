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
    except Exception as e:
        return f"Error fetching status: {e}"

def get_agent_fingerprint(data):
    """
    Generate a deterministic fingerprint for agent states.
    Ignores volatile fields like 'reported_at'.
    Sorts agents by ID to be stable even if API order changes.
    """
    if not isinstance(data, list):
        return str(data)
    
    # Sort agents by ID for stable fingerprinting
    sorted_agents = sorted(data, key=lambda x: str(x.get('agent_id', '')))
    
    # Select fields that represent "semantic" state changes
    fingerprint_data = []
    for agent in sorted_agents:
        fingerprint_data.append({
            'agent_id': agent.get('agent_id'),
            'task_name': agent.get('task_name'),
            'status': agent.get('status'),
            'progress': agent.get('progress'),
            'message': agent.get('message')
        })
    
    return hashlib.md5(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()

def format_table(data):
    if not isinstance(data, list):
        return data
        
    table_data = []
    for agent in data:
        # Convert reported_at for readability
        reported_at = agent.get('reported_at', '')
        if reported_at:
            try:
                dt = datetime.fromisoformat(reported_at.replace('Z', '+00:00'))
                reported_at = dt.strftime('%H:%M:%S')
            except:
                pass
                
        table_data.append([
            agent.get('agent_id'),
            agent.get('task_name'),
            agent.get('status'),
            f"{agent.get('progress', 0)}%",
            agent.get('message', ''),
            reported_at
        ])
        
    headers = ["Agent ID", "Task Name", "Status", "Progress", "Message", "Time (UTC)"]
    return tabulate(table_data, headers=headers, tablefmt="grid")

def main():
    parser = argparse.ArgumentParser(description="Agent Monitor CLI")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--once", action="store_true", help="Fetch status once and exit")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--interval", type=float, default=2.0, help="Initial polling interval in seconds")
    parser.add_argument("--max-interval", type=float, default=60.0, help="Maximum polling interval for backoff")
    parser.add_argument("--backoff-factor", type=float, default=1.5, help="Backoff multiplier when no changes detected")
    
    args = parser.parse_args()
    
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
                current_interval = min(current_interval * args.backoff_factor, args.max_interval)
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
                    print(f"Agent Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    if current_interval > args.interval:
                        print(f"(Backing off: {current_interval:.1f}s interval)")
                print(format_table(data))
                
            if args.once:
                break
                
            time.sleep(current_interval)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
