웹 호스팅(대시보드)과 CLI 양쪽에서 에이전트들의 상태를 확인할 수 있도록 시스템을 확장해 보겠습니다. 이를 위해 **FastAPI**를 사용하여 MCP 서버 기능과 Web API 기능을 통합한 하이브리드 서버를 구축합니다.

---

## 🏗️ 시스템 아키텍처

1. **Backend (FastAPI):** MCP 서버 역할을 수행하면서 동시에 상태 데이터를 제공하는 REST API를 노출합니다.
2. **Web Dashboard:** 브라우저에서 `http://localhost:8000`에 접속하여 실시간 테이블을 확인합니다.
3. **CLI Tool:** 터미널에서 명령어를 입력해 현재 상태를 즉시 출력합니다.

---

## 1. 서버 코드 (`server.py`)

MCP와 Web 서버를 동시에 구동하기 위해 `FastAPI`와 `mcp` 라이브러리를 사용합니다.

```python
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from mcp.server.fastmcp import FastMCP
import pandas as pd
from datetime import datetime

# 1. MCP 서버 설정
mcp = FastMCP("AgentMonitor")
db = {}

@mcp.tool()
def report_status(agent_id: str, task: str, status: str, progress: int, msg: str):
    """에이전트가 상태를 보고할 때 호출 (MCP 도구)"""
    db[agent_id] = {
        "agent_id": agent_id,
        "task": task,
        "status": status,
        "progress": progress,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "message": msg
    }
    return f"Status updated for {agent_id}"

# 2. FastAPI 설정 (Web & CLI용 API)
app = FastAPI()

@app.get("/api/status")
def get_status_api():
    """CLI와 Web에서 호출할 데이터 API"""
    return list(db.values())

@app.get("/", response_class=HTMLResponse)
def web_dashboard():
    """웹 브라우저 확인용 대시보드"""
    html_content = """
    <html>
        <head>
            <title>Agent Monitor</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <meta http-equiv="refresh" content="5"> </head>
        <body class="bg-gray-900 text-white p-8">
            <h1 class="text-3xl font-bold mb-6 text-blue-400">🤖 Agent Activity Dashboard</h1>
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="border-b border-gray-700">
                        <th class="p-3">ID</th><th class="p-3">Task</th>
                        <th class="p-3">Status</th><th class="p-3">Progress</th>
                        <th class="p-3">Last Update</th><th class="p-3">Message</th>
                    </tr>
                </thead>
                <tbody>
    """
    for aid, info in db.items():
        color = "text-green-400" if info['status'] == "completed" else "text-yellow-400"
        html_content += f"""
            <tr class="border-b border-gray-800">
                <td class="p-3 font-mono">{aid}</td>
                <td class="p-3">{info['task']}</td>
                <td class="p-3 font-bold {color}">{info['status']}</td>
                <td class="p-3">{info['progress']}%</td>
                <td class="p-3 text-gray-400">{info['timestamp']}</td>
                <td class="p-3 text-sm italic text-gray-300">{info['message']}</td>
            </tr>
        """
    
    html_content += "</tbody></table></body></html>"
    return html_content

if __name__ == "__main__":
    # MCP와 Web을 동시에 실행하기 위해 uvicorn 사용
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 2. CLI 도구 (`monitor.py`)

터미널에서 간단하게 `python monitor.py`를 실행하여 현재 상태를 표 형태로 출력합니다.

```python
import requests
from tabulate import tabulate
import time
import os

def fetch_status():
    try:
        response = requests.get("http://localhost:8000/api/status")
        if response.status_code == 200:
            data = response.json()
            if not data:
                print("활동 중인 에이전트가 없습니다.")
                return
            
            os.system('cls' if os.name == 'nt' else 'clear') # 화면 초기화
            print(f"--- Agent Monitor CLI ({time.strftime('%H:%M:%S')}) ---")
            print(tabulate(data, headers="keys", tablefmt="grid"))
        else:
            print("서버 응답 오류")
    except Exception as e:
        print(f"서버에 연결할 수 없습니다: {e}")

if __name__ == "__main__":
    # 2초마다 갱신하며 감시
    while True:
        fetch_status()
        time.sleep(2)
```

---

## 3. 설치 및 실행 방법

### **1단계: 라이브러리 설치**

```bash
pip install fastapi uvicorn fastmcp pandas requests tabulate
```

### **2단계: 서버 실행**

```bash
python server.py
```

* **Web 접속:** `http://localhost:8000` (자동 갱신 대시보드)
* **API 확인:** `http://localhost:8000/api/status`

### **3단계: CLI 확인**

새 터미널을 열고 아래 명령어를 실행하세요.

```bash
python monitor.py
```

---

## 💡 활용 팁

1. **Web 호스팅:** 이 코드를 Replit, Heroku, 또는 개인 서버(AWS/GCP)에 올리면 외부에서도 에이전트 상태를 확인할 수 있습니다. (단, MCP 연결을 위해서는 서버 주소를 공인 IP나 도메인으로 설정해야 합니다.)
2. **데이터 보존:** 현재는 메모리 기반이라 서버를 끄면 데이터가 날아갑니다. `db` 변수 대신 `sqlite3`나 `json` 파일 저장 로직을 추가하면 과거 이력을 남길 수 있습니다.
3. **에이전트 연결:** Claude Desktop 설정에서 `args`에 `server.py` 경로를 입력하면, 에이전트가 코딩 도중 "상태 보고해"라는 명령을 받으면 자동으로 `report_status` 툴을 써서 이 대시보드에 데이터를 쏘게 됩니다.

이제 에이전트들이 일하는 동안 편하게 **웹 브라우저**나 **터미널**을 띄워놓고 구경만 하시면 됩니다! 추가로 필요한 UI 기능이나 필터링 옵션이 있을까요?
