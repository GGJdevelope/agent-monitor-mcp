import argparse
import json
import time
import requests
from tabulate import tabulate
from datetime import datetime

def fetch_status(api_url):
    try:
        response = requests.get(f"{api_url}/api/agents")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return f"Error fetching status: {e}"

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
    parser.add_argument("--interval", type=int, default=2, help="Polling interval in seconds")
    
    args = parser.parse_args()
    
    try:
        while True:
            data = fetch_status(args.url)
            
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                if not args.once:
                    # Clear screen for watch mode
                    print("\033[H\033[J", end="")
                    print(f"Agent Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(format_table(data))
                
            if args.once:
                break
                
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
