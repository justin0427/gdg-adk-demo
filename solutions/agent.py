"""
soc_agent/agent.py — 用 Google ADK 打造的「資安 Log 分析 Agent」

這支 Agent 做的事，跟你平常在 SOC(資安維運中心)裡做的一樣：
    使用者用「自然語言」問問題 → Agent 判斷該呼叫哪個工具 → 工具做分析 → Agent 寫成報告

三個工具(Tools)：
    1. list_orgs()             ：這批 log 裡有哪些公司(租戶)？
    2. classify_logs(date)     ：依公司分類彙整，並自動標記可疑行為。   ← 核心「分類」功能
    3. get_org_detail(org)     ：把某一家公司的細節攤開，給 Agent 寫深入報告。

設計重點：
- 工具用「純 Python」做確定性的計算(聚合、規則比對)，穩、快、可測。
- LLM(Agent) 負責「聽懂人話 + 決定呼叫哪個工具 + 把結果寫成報告」。
- 完全可離線：資料是本機合成 log，模型走本機 Ollama。
"""

import os
import re
import json
from datetime import datetime
from collections import defaultdict

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# =============================================================================
# 1) 模型設定 —— 走「本機 Ollama」的 OpenAI 相容介面(可用環境變數覆寫)
# =============================================================================
# Ollama 啟動後預設會開 http://localhost:11434 ，其 /v1 路徑相容 OpenAI API。
# 課堂上如果講師有架共用 endpoint，只要改 OLLAMA_API_BASE 環境變數即可。
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")   # Ollama 不驗 key，但 LiteLLM 需要有值
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")    # 建議選「支援 tool calling」的模型

# LiteLLM 透過這兩個環境變數找到 OpenAI 相容端點
os.environ["OPENAI_API_BASE"] = OLLAMA_API_BASE
os.environ["OPENAI_API_KEY"] = OLLAMA_API_KEY

# =============================================================================
# 2) 讀取合成 log
# =============================================================================
_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "access_logs.json")


def _load_logs():
    """讀取 data/access_logs.json；若不存在，回傳空清單並提示先產生資料。"""
    if not os.path.exists(_DATA_PATH):
        return []
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# 3) 風險評分引擎 —— 沿用真實 SOC 常用的評分表(Risk Scoring Rubric)
# =============================================================================
# 規則：比對 API 字串裡的攻擊特徵，命中就給分。
# 標「CRS」的規則直接取自 OWASP Core Rule Set——全球 WAF 共同維護的官方規則庫
# （github.com/coreruleset/coreruleset，Apache-2.0 授權）。
RISK_RULES = [
    # (風險類型, 分數, 正規表示式)
    # CRS 規則 942270：經典 SQL Injection（union … select … from，想撈出別張表）
    ("SQL Injection", 10, re.compile(r"(?i)union.*?select.*?from")),
    # CRS 規則 942160：盲注偵測（用 sleep()/benchmark() 拖時間探測）
    ("SQL Injection", 10, re.compile(r"(?i)(sleep\s*?\(.*?\)|benchmark\s*?\(.*?,.*?\))")),
    # 自訂補充：引號繞過（' or '1'='1）、註解截斷（--）、破壞性語句
    ("SQL Injection", 10, re.compile(r"(?i)('\s*or\s*'?1'?\s*=\s*'?1|--|\bdrop\s+table|information_schema)")),
    ("路徑遍歷 Path Traversal", 9, re.compile(r"(?i)(\.\./|\.\.%2f|/etc/passwd|win\.ini|/proc/self)")),
    ("敏感路徑存取", 8, re.compile(r"(?i)(/\.env|/\.git|/\.aws|wp-login|phpmyadmin|backup\.(zip|sql)|config\.php)")),
    # CRS 規則 941110：XSS Script Tag 向量（<script …>）
    ("跨站腳本 XSS", 6, re.compile(r"(?i)<script[^>]*>[\s\S]*?")),
]

# 風險等級(取所有命中項目的最高分)
def _risk_level(score: int) -> str:
    if score >= 8:
        return "🔴 高風險"
    if score >= 5:
        return "🟡 中風險"
    return "🟢 低風險"


def _scan_entry(api: str):
    """對單筆 API 字串比對所有規則，回傳命中的 [(類型, 分數), ...]。"""
    hits = []
    for name, score, pattern in RISK_RULES:
        if pattern.search(api or ""):
            hits.append((name, score))
    return hits


# 高頻偵測門檻：同一個 IP 在「任意 60 秒視窗」內達到這個請求數，視為爆量存取。
# (正常使用者一整天可能上百次，但攤在 12 小時；爬蟲則是 1 分鐘打好幾十次。用「速率」才分得開。)
BURST_WINDOW_SEC = 60
BURST_THRESHOLD = 50


def _burst_ips(records) -> set:
    """找出「短時間內爆量存取」的 IP：任一 60 秒視窗內請求數 >= 門檻。"""
    times_by_ip = defaultdict(list)
    for r in records:
        try:
            ts = datetime.strptime(r["time"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
        except ValueError:
            continue
        times_by_ip[r["ip"]].append(ts)

    hot = set()
    for ip, times in times_by_ip.items():
        times.sort()
        left = 0
        for right in range(len(times)):
            while times[right] - times[left] > BURST_WINDOW_SEC:
                left += 1
            if right - left + 1 >= BURST_THRESHOLD:
                hot.add(ip)
                break
    return hot


# =============================================================================
# 4) ADK 工具(Tools) —— 這些函式會被 Agent 依需求呼叫
# =============================================================================
def list_orgs() -> dict:
    """列出這批日誌中出現的所有公司(租戶)與各自的請求數量。

    當使用者問「有哪些公司 / 有誰的資料 / 總覽」時使用。

    Returns:
        dict: {"orgs": [{"org": 名稱, "requests": 數量}, ...], "total": 總筆數}
    """
    logs = _load_logs()
    counter = defaultdict(int)
    for r in logs:
        counter[r["org"]] += 1
    orgs = [{"org": k, "requests": v} for k, v in sorted(counter.items())]
    return {"orgs": orgs, "total": len(logs)}


def classify_logs(date: str = "") -> dict:
    """依「公司(org)」分類彙整日誌，並自動標記每家公司的可疑行為與風險等級。

    這是核心分類功能：把一大包散亂的 log，整理成「每家公司一張摘要卡」。

    Args:
        date: 選填。指定日期 (YYYY-MM-DD) 只看當天；留空代表全部。

    Returns:
        dict: 每家公司的請求數、不重複 IP 數、存取的 API 數、時間範圍，
              以及偵測到的風險類型、最高風險分數與等級。
    """
    logs = _load_logs()
    if not logs:
        return {"error": "找不到日誌資料，請先執行：python generate_logs.py"}

    if date:
        logs = [r for r in logs if r["time"].startswith(date)]

    by_org = defaultdict(lambda: {
        "requests": 0, "ips": set(), "apis": set(),
        "times": [], "risks": defaultdict(int), "bad_ips": set(),
    })

    for r in logs:
        o = by_org[r["org"]]
        o["requests"] += 1
        o["ips"].add(r["ip"])
        o["apis"].add(r["api"].split("?")[0])   # 只看路徑，忽略 query
        o["times"].append(r["time"])
        for name, score in _scan_entry(r["api"]):
            o["risks"][name] = max(o["risks"][name], score)
            o["bad_ips"].add(r["ip"])

    # 先算出所有「爆量 IP」(用整批資料算速率)
    burst = _burst_ips(logs)

    result = []
    for org, o in sorted(by_org.items()):
        # 額外規則：短時間爆量存取視為「高頻/密集存取」(5 分)
        org_burst_ips = {ip for ip in o["ips"] if ip in burst}
        if org_burst_ips:
            o["risks"]["高頻/密集存取"] = max(o["risks"].get("高頻/密集存取", 0), 5)
            o["bad_ips"].update(org_burst_ips)

        max_score = max(o["risks"].values(), default=0)
        result.append({
            "org": org,
            "requests": o["requests"],
            "unique_ips": len(o["ips"]),
            "distinct_apis": len(o["apis"]),
            "time_range": [min(o["times"]), max(o["times"])],
            "detected_risks": [{"type": k, "score": v} for k, v in
                               sorted(o["risks"].items(), key=lambda x: -x[1])],
            "suspicious_ips": sorted(o["bad_ips"]),
            "max_risk_score": max_score,
            "risk_level": _risk_level(max_score),
        })

    return {"date": date or "全部", "orgs": result}


def get_org_detail(org: str) -> dict:
    """攤開單一公司的細節，供撰寫深入資安報告使用。

    當使用者要求「分析 / 深入 / 生報告 / 某公司發生什麼事」時使用。

    Args:
        org: 公司名稱，例如 "Initech"。

    Returns:
        dict: 該公司每個 IP 的請求數、Top API、可疑請求範例與風險評分。
    """
    logs = [r for r in _load_logs() if r["org"].lower() == org.lower()]
    if not logs:
        return {"error": f"找不到公司 '{org}' 的資料。可先用 list_orgs 查看有哪些公司。"}

    per_ip = defaultdict(lambda: {"count": 0, "apis": defaultdict(int),
                                  "risks": defaultdict(int), "samples": []})
    for r in logs:
        p = per_ip[r["ip"]]
        p["count"] += 1
        p["apis"][r["api"].split("?")[0]] += 1
        for name, score in _scan_entry(r["api"]):
            p["risks"][name] = max(p["risks"][name], score)
            if len(p["samples"]) < 5:
                p["samples"].append({"time": r["time"], "method": r["method"], "api": r["api"]})

    burst = _burst_ips(logs)

    ip_report = []
    for ip, p in sorted(per_ip.items(), key=lambda x: -x[1]["count"]):
        risks = dict(p["risks"])
        if ip in burst:
            risks["高頻/密集存取"] = max(risks.get("高頻/密集存取", 0), 5)
        max_score = max(risks.values(), default=0)
        ip_report.append({
            "ip": ip,
            "requests": p["count"],
            "top_apis": sorted(p["apis"].items(), key=lambda x: -x[1])[:5],
            "risks": [{"type": k, "score": v} for k, v in sorted(risks.items(), key=lambda x: -x[1])],
            "risk_level": _risk_level(max_score),
            "sample_requests": p["samples"],
        })

    overall = max((ip["risks"][0]["score"] if ip["risks"] else 0) for ip in ip_report) if ip_report else 0
    return {
        "org": org,
        "total_requests": len(logs),
        "overall_risk_level": _risk_level(overall),
        "ip_breakdown": ip_report,
    }


# =============================================================================
# 5) 建立 ADK Agent
# =============================================================================
SYSTEM_INSTRUCTION = """
你是一位資深資安分析師 (SOC Analyst)。你的工作是協助使用者分析 API 存取日誌、找出可疑行為，並產出專業的資安分析報告。

## 可用工具
- list_orgs：查詢這批日誌有哪些公司。
- classify_logs：依公司分類彙整，並自動標記風險。適合「總覽 / 全部分類 / 有沒有異常」。
- get_org_detail：攤開某公司的細節。適合「分析某公司 / 生報告 / 深入調查」。

## 風險評分基準 (Risk Scoring Rubric)
- SQL Injection：10 分 🔴
- 路徑遍歷 Path Traversal：9 分 🔴
- 敏感路徑存取：8 分 🔴
- API 掃描 / 探測：7 分 🟡
- 跨站腳本 XSS：6 分 🟡
- 高頻 / 密集存取：5 分 🟡
- 整體風險等級 = 所有偵測項目中的最高分。判定：分數 ≥ 8 → 🔴 高風險；5–7 → 🟡 中風險；< 5 → 🟢 低風險。

## 產出報告時的規則
當使用者要求「分析某公司」或「生報告」時，請先呼叫 get_org_detail，再用 Markdown 寫出報告，需包含：
1. **執行摘要**：一句話講清楚整體狀況與最高風險等級。
2. **風險評分摘要**：列出偵測到的風險類型、分數與 emoji 指標 (🔴/🟡/🟢)。
3. **可疑 IP 剖析**：針對可疑 IP 說明它做了什麼(附請求範例)、對應到哪種攻擊手法。
4. **建議措施**：針對發現給出具體、可執行的防禦建議(如：阻擋 IP、參數化查詢、限制敏感路徑、速率限制)。

若未偵測到任何威脅，明確指出「🟢 低風險 — 未發現 SQL Injection / 路徑遍歷 / XSS 等攻擊特徵」。請用繁體中文回答。
"""

# ADK 的 `adk web` / `adk run` 會自動尋找名為 root_agent 的變數
root_agent = Agent(
    model=LiteLlm(model=f"openai/{OLLAMA_MODEL}"),
    name="soc_agent",
    description="分析 API 存取日誌、偵測可疑行為並產出資安報告的 Agent",
    instruction=SYSTEM_INSTRUCTION,
    tools=[list_orgs, classify_logs, get_org_detail],
)


# =============================================================================
# 6) 不接 LLM 也能先測工具 —— 直接 `python soc_agent/agent.py`
# =============================================================================
if __name__ == "__main__":
    print("== list_orgs ==")
    print(json.dumps(list_orgs(), ensure_ascii=False, indent=2))
    print("\n== classify_logs ==")
    print(json.dumps(classify_logs(), ensure_ascii=False, indent=2))
