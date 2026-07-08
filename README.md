# 用 Google ADK ＋ 地端 LLM 打造你的第一支 AI Agent

GDG on Campus 的一小時實作課程：用 **Google ADK (Agent Development Kit)** 搭配**地端 LLM（Ollama）**，從零打造一支「資安 Log 分析 Agent」。使用者用自然語言提問，Agent 自己決定呼叫哪個工具，產出資安分析報告——模型全程跑在自己的機器上，敏感日誌不必送雲端，也不需要任何 API Key。

> 本 demo 使用**合成資料**（虛構公司 Acme / Globex / Initech / Umbrella / Cyberdyne，IP 皆為 RFC 5737 文件保留網段），可安全公開。

---

## 你會做出什麼

```
你：「幫我看一下這批 log，有沒有異常？」
Agent →（呼叫 classify_logs）→ 回你一張各公司的風險總覽表

你：「幫我分析 Initech 的資安狀況，寫一份報告」
Agent →（呼叫 get_org_detail）→ 產出含風險評分、可疑 IP 剖析、建議措施的 Markdown 報告
```

課程裡還藏了第五間公司——它顯示「低風險」，但其實正在被一種現有規則抓不到的攻擊手法入侵。找不找得出來、看不看得穿「規則沒有響」不等於「真的沒事」，是這堂課後半段的重頭戲。

---

## 這個 repo 給誰用

- **只想跑跑看 demo**：照下面「快速開始」做就好。
- **要發給學員**：課前發 `PREWORK.html`（環境準備、下載這個 repo）——排版好的自包含網頁，含語法高亮、複製鈕、深淺色自動切換，直接用瀏覽器打開即可。上課用的實作講義不放在這個公開 repo 裡，現場改用內網主機發布。

---

## 快速開始

以下指令以 Windows 為主；macOS 請把 `python` 換成 `python3`，把 `pip install ...` 換成 `python3 -m pip install ...`，並用 `source .venv/bin/activate` 啟動虛擬環境（`PREWORK.html` 裡每個指令方塊都有 macOS / Windows 切換鈕，照著切就好）。

```bash
# 1. 建立並啟動虛擬環境，然後安裝套件
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 安裝 Ollama（https://ollama.com/）後下載模型
ollama pull gemma4:e4b

# 3. 環境健檢（六項一次檢查，有 FAIL 會告訴你怎麼修）
python check_env.py

# 4. 產生合成日誌 → data/access_logs.json
python generate_logs.py

# 5.（可選）先不接 LLM，直接看工具輸出，確認資料 OK
python soc_agent/agent.py

# 6. 啟動 ADK 的對話 / 除錯介面
adk web
```

瀏覽器開 `http://localhost:8000` → 左上選 `soc_agent` → 開始用自然語言提問。預設連本機 Ollama（`http://localhost:11434/v1`）與 `gemma4:e4b`，本機跑就**不用改任何設定**。

> `gemma4`/`gemma3n` 系列在 Ollama 的 OpenAI 相容 streaming tool_calls 上有已知回報問題（尤其 system prompt ＋ tools 一起用時，就是這支 Agent 的架構）。上場前務必用 `python check_env.py --llm` 實測過，失敗就換備用模型：`ollama pull qwen2.5:7b`（或 `llama3.1:8b`），改設 `OLLAMA_MODEL` 環境變數即可，不用動程式碼。

---

## 想從零練習打造 Agent（code-along）

repo 裡的 `soc_agent/agent.py` 預設是**完成版**，方便直接執行。想跟著上課講義從零打造，用 `reset.py` 切換：

```bash
python reset.py start   # 換成空白骨架（含分節標記，照講義一節一節貼），原檔自動備份成 .bak
python reset.py done    # 隨時換回完成版——卡住、改壞了、跟不上進度都可以用這個 30 秒歸隊
```

---

## 現場同步講義（內網 live server）

上課時想讓學生看同一份網頁講義，並且你一存檔、學生端就自動刷新，由你的電腦開一個內網 live server：

```bash
python3 live_server.py --host 0.0.0.0 --port 8008
```

查你自己電腦的內網 IP（Wi-Fi 用 `en0`，有線網路可能要改 `en1`）：

```bash
ipconfig getifaddr en0
```

假設查到 `192.168.1.23`，學生就開 `http://192.168.1.23:8008`。

這個公開 repo 裡預設只有 `PREWORK.md` 這一份講義；正式上課用的實作講義是另外準備、不放在這個 repo 裡的，把講義檔案放進資料夾、在 `live_server.py` 開頭的 `PAGES` 列表加一行，存檔就會自動重建對應的 HTML，已打開講義的瀏覽器會自動刷新。

假設查到你電腦的內網 IP 是 `192.168.1.23`，學生課前開 `http://192.168.1.23:8008/PREWORK.html` 就能看到即時更新的前置作業頁面。

注意：你和學生必須在同一個 Wi-Fi / LAN；macOS 防火牆跳出提示時要允許 Python 接受連線；學校 Wi-Fi 若開了 AP isolation／client isolation 導致學生連不到，改用 `cloudflared tunnel --url http://localhost:8008` 或 `ngrok http 8008`；上課前務必先用手機連同一個 Wi-Fi 測試過。

---

## 設定（只有要覆寫預設時才需要）

用環境變數覆寫，或把 `.env.example` 複製成 `soc_agent/.env`：

| 變數 | 預設 | 說明 |
|---|---|---|
| `OLLAMA_API_BASE` | `http://localhost:11434/v1` | Ollama / 共用伺服器的 OpenAI 相容端點 |
| `OLLAMA_API_KEY`  | `ollama` | Ollama 不驗證，隨便填 |
| `OLLAMA_MODEL`    | `gemma4:e4b` | 要用的模型（需支援 tool calling；備用：`qwen2.5:7b` / `llama3.1:8b`） |

```bash
export OLLAMA_API_BASE="http://<共用伺服器>:11434/v1"
export OLLAMA_MODEL="gemma4:e4b"
```

---

## 試試這些提問

- 「這批 log 裡有哪些公司？」
- 「幫我把 log 分類，看看每家公司的風險。」
- 「分析 Initech 的資安狀況，寫一份報告。」
- 「Umbrella 有沒有被攻擊？」
- 「哪一家最危險？為什麼？」

做完基本流程後，也可以試著自己揪出第五間公司 Cyberdyne 藏的那個攻擊——現有的兩層規則（內容比對、短時間爆量）都抓不到它，講義的「換你試」會給提示。

---

## 專案結構

```
gdg-adk-demo/
├── PREWORK.md / .html          上課前置作業（獨立頁面：裝環境、下載模型、跑健檢）
├── build_html.py               把 .md 講義轉成排版好的自包含 .html
├── live_server.py              內網即時刷新伺服器（教室現場用）
├── check_env.py                一鍵環境健檢（六項）
├── reset.py                    骨架 / 完成版切換（code-along 用）
├── generate_logs.py            產生合成日誌（含 5 種攻擊，其中 1 種現有規則抓不到）
├── requirements.txt
├── .env.example
├── data/
│   └── access_logs.json       執行 generate_logs.py 後產生
├── images/                     講義示意圖與 GDG on Campus logo（深淺兩版）
├── soc_agent/
│   ├── __init__.py            讓 adk web 認得這個 agent 套件
│   └── agent.py                工具 + 風險評分引擎 + root_agent（完成版）
├── solutions/agent.py           完成版原始碼（reset.py done 用）
└── starter/agent_skeleton.py    code-along 空白骨架（reset.py start 用）
```

---

## 疑難排解

| 症狀 | 解法 |
|---|---|
| `adk web` 看不到 agent | 確認在 `gdg-adk-demo/` 目錄下執行，且 `soc_agent/__init__.py` 存在；`reset.py start` 後半途沒貼完也會這樣，先 `reset.py done` 歸隊 |
| 找不到日誌資料 | 先跑 `python generate_logs.py` |
| 連線錯誤 / Connection refused | Ollama 沒開（`ollama serve`），或 `OLLAMA_API_BASE` 指錯 |
| Agent 不會呼叫工具 / 亂回答 / 回覆裡混進奇怪符號 | 模型不支援 tool calling 或有已知相容性問題，換 `qwen2.5:7b` 或 `llama3.1:8b` |
| `adk web` 埠號被占用 | `adk web --port 8001` |
| `pip install` 出現 `externally-managed-environment` | 忘了先啟動虛擬環境，回到快速開始第 1 步重跑 |
| 內網 live server 學生連不到 | 確認同一 Wi-Fi、macOS 防火牆允許連線；學校 Wi-Fi 有 client isolation 就改用 cloudflared/ngrok |
