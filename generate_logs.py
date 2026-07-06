"""
generate_logs.py — 產生示範用的「合成 API 存取日誌」

用途：
- 為 GDG on Campus 課程 demo 產生一份「長得像真的、但完全是假的」存取日誌。
- 欄位刻意對齊真實世界的 web / API log：time, org, role, api, method, ip。
- 內含幾筆「刻意注入的可疑行為」，讓 Agent 有東西可以分類與示警。

特色（為了教學）：
- random.seed 固定 → 每個人跑出來的資料一模一樣，方便對答案。
- IP 一律使用「文件保留網段」(TEST-NET, RFC 5737)：192.0.2.x / 198.51.100.x / 203.0.113.x
  這些網段被 IANA 保留給文件範例，不會對應到任何真實主機，最適合當假資料。
- 公司名稱用大家都知道的「虛構公司」(Acme / Globex / Initech / Umbrella / Cyberdyne)，一眼就知道是假的。
- 五家公司裡包含正常流量與幾筆刻意注入的可疑行為，方便課堂示範規則能抓到什麼、
  又可能漏掉什麼。

執行：
    python generate_logs.py
輸出：
    data/access_logs.json   （JSON 陣列，依時間排序）
"""

import os
import json
import random
from datetime import datetime, timedelta, timezone

# 固定亂數種子 → 可重現，全班資料一致
random.seed(42)

# 資料的「基準日」：固定一天，方便課堂上用日期查詢
BASE_DATE = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "access_logs.json")

# 四家虛構公司（多租戶情境 → 對應真實專案的「依機構分類」）
ORGS = ["Acme", "Globex", "Initech", "Umbrella"]

ROLES = ["member", "admin", "guest", "service"]

# 各公司的「正常」API 路徑
NORMAL_APIS = [
    "/api/login",
    "/api/logout",
    "/api/profile",
    "/api/products",
    "/api/orders",
    "/api/search",
    "/api/inventory",
    "/api/notifications",
    "/static/app.js",
    "/static/style.css",
]

# 每家公司「正常使用者」的來源 IP（文件保留網段）
NORMAL_IPS = {
    "Acme":     ["203.0.113.10", "203.0.113.11", "203.0.113.12"],
    "Globex":   ["198.51.100.20", "198.51.100.21", "198.51.100.22"],
    "Initech":  ["192.0.2.30", "192.0.2.31", "192.0.2.32"],
    "Umbrella": ["203.0.113.40", "203.0.113.41", "203.0.113.42"],
}


def iso(ts: datetime) -> str:
    """輸出成 ISO-8601 (帶毫秒與 Z)，對齊常見 log 格式。"""
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{ts.microsecond // 1000:03d}Z"


def entry(ts, org, role, api, method, ip):
    return {
        "time": iso(ts),
        "org": org,
        "role": role,
        "api": api,
        "method": method,
        "ip": ip,
    }


def gen_normal(records):
    """產生一整天、四家公司的正常流量。"""
    for org in ORGS:
        ips = NORMAL_IPS[org]
        # 每家公司約 250~350 筆正常請求，散布在早上 8 點到晚上 8 點
        n = random.randint(250, 350)
        for _ in range(n):
            minute_of_day = random.randint(8 * 60, 20 * 60)
            ts = BASE_DATE + timedelta(minutes=minute_of_day,
                                       seconds=random.randint(0, 59),
                                       milliseconds=random.randint(0, 999))
            api = random.choice(NORMAL_APIS)
            method = "POST" if api == "/api/login" else "GET"
            records.append(entry(ts, org, random.choice(ROLES), api, method,
                                 random.choice(ips)))


def gen_sqli(records):
    """注入①：Initech 有一個 IP 嘗試 SQL Injection。"""
    ip = "198.51.100.66"
    payloads = [
        "/api/login?user=admin'--",
        "/api/orders?id=1 UNION SELECT username,password FROM users",
        "/api/search?q=1' OR '1'='1",
        "/api/orders?id=1; DROP TABLE users",
    ]
    start = BASE_DATE + timedelta(hours=2, minutes=13)
    for i in range(12):
        ts = start + timedelta(seconds=i * 7)
        api = payloads[i % len(payloads)]
        records.append(entry(ts, "Initech", "guest", api, "GET", ip))


def gen_path_traversal(records):
    """注入②：Umbrella 有一個 IP 嘗試路徑遍歷 / 讀取敏感檔。"""
    ip = "203.0.113.99"
    payloads = [
        "/api/download?file=../../../../etc/passwd",
        "/api/report?path=..%2f..%2f..%2fwindows/win.ini",
        "/api/export?name=../../../../proc/self/environ",
    ]
    start = BASE_DATE + timedelta(hours=3, minutes=41)
    for i in range(9):
        ts = start + timedelta(seconds=i * 5)
        records.append(entry(ts, "Umbrella", "guest",
                             payloads[i % len(payloads)], "GET", ip))


def gen_scanning(records):
    """注入③：Globex 有一個 IP 在掃描敏感路徑（找後門 / 設定檔）。"""
    ip = "192.0.2.44"
    paths = [
        "/.env", "/.git/config", "/wp-login.php", "/phpmyadmin/",
        "/admin", "/backup.zip", "/config.php.bak", "/.aws/credentials",
    ]
    start = BASE_DATE + timedelta(hours=1, minutes=5)
    for i, p in enumerate(paths):
        ts = start + timedelta(seconds=i * 2)
        records.append(entry(ts, "Globex", "guest", p, "GET", ip))


def gen_high_frequency(records):
    """注入④：Acme 有一個 IP 高頻爬取 /api/search（1 分鐘內 200 次）。"""
    ip = "203.0.113.7"
    start = BASE_DATE + timedelta(hours=5, minutes=30)
    for i in range(200):
        ts = start + timedelta(milliseconds=i * 300)  # 每 0.3 秒一次
        records.append(entry(ts, "Acme", "service",
                             f"/api/search?page={i}", "GET", ip))


# =============================================================================
# 延伸情境：一個現有規則抓不到的「低頻長時間」登入行為
# =============================================================================
# 前面四種攻擊都有明顯的內容特徵（SQL 語法、../、敏感路徑）或短時間爆量，
# 才會被 RISK_RULES 或 _burst_ips 抓到。這一種刻意反過來：
# 攻擊打的是完全正常的 API（/api/login），內容規則沒有東西可以比對；
# 而且刻意拖了 3 小時、每隔幾分鐘才打一次，任何 60 秒視窗都湊不到 _burst_ips
# 的門檻（50 次）。這才是真實世界最難防的那種：低頻、長時間、內容正常。
FIFTH_ORG = "Cyberdyne"
FIFTH_NORMAL_IPS = ["198.51.100.50", "198.51.100.51", "198.51.100.52"]
FIFTH_ATTACK_IP = "198.51.100.77"

ORGS_ALL = ORGS + [FIFTH_ORG]


def gen_cyberdyne_normal(records):
    """Cyberdyne 的正常流量（跟其他四家公司同一套邏輯，份量小一點）。"""
    n = random.randint(120, 180)
    for _ in range(n):
        minute_of_day = random.randint(8 * 60, 20 * 60)
        ts = BASE_DATE + timedelta(minutes=minute_of_day,
                                   seconds=random.randint(0, 59),
                                   milliseconds=random.randint(0, 999))
        api = random.choice(NORMAL_APIS)
        method = "POST" if api == "/api/login" else "GET"
        records.append(entry(ts, FIFTH_ORG, random.choice(ROLES), api, method,
                             random.choice(FIFTH_NORMAL_IPS)))


def gen_slow_bruteforce(records):
    """低頻長時間登入嘗試，同一 IP 花 3 小時、每隔幾分鐘打一次 /api/login。

    刻意躲開兩種現有防線：
    - 內容規則：/api/login 是正常 API，沒有可疑字串可比對。
    - 爆量規則：間隔以分鐘計，任何 60 秒視窗內都只有 1 次請求，遠低於 _burst_ips 門檻。
    """
    start = BASE_DATE + timedelta(hours=9)
    t = start
    end = start + timedelta(hours=3)
    while t < end:
        records.append(entry(t, FIFTH_ORG, "guest", "/api/login", "POST", FIFTH_ATTACK_IP))
        t += timedelta(minutes=random.uniform(2, 6))


def main():
    records = []
    gen_normal(records)
    gen_sqli(records)
    gen_path_traversal(records)
    gen_scanning(records)
    gen_high_frequency(records)
    gen_cyberdyne_normal(records)
    gen_slow_bruteforce(records)

    # 依時間排序，像真的 log 一樣
    records.sort(key=lambda r: r["time"])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"已產生 {len(records)} 筆合成日誌 → {OUTPUT_PATH}")
    print(f"   日期：{BASE_DATE.date()}　公司：{', '.join(ORGS_ALL)}")
    print("   內含 4 種容易辨識的可疑行為：SQL Injection / 路徑遍歷 / 敏感路徑掃描 / 高頻爬取")


if __name__ == "__main__":
    main()
