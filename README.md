# SOC Agent — Google ADK ＋ 地端 LLM 一小時實作 Demo

用 **Google ADK (Agent Development Kit)** 搭配**地端 LLM（Ollama）**打造一支「資安 Log 分析 Agent」：
使用者用自然語言提問 → Agent 自己決定呼叫哪個工具 → 產出資安分析報告。
模型全程跑在自己的機器上，敏感日誌不必送雲端、不需要任何 API Key。

> 📌 本 demo 使用**合成資料**（虛構公司 Acme / Globex / Initech / Umbrella / Cyberdyne，IP 皆為 RFC 5737 文件保留網段），可安全公開。

---

## 你會做出什麼

```
你：「幫我看一下這批 log，有沒有異常？」
Agent →（呼叫 classify_logs）→ 回你一張各公司的風險總覽表

你：「幫我分析 Initech 的資安狀況，寫一份報告」
Agent →（呼叫 get_org_detail）→ 產出含風險評分、可疑 IP 剖析、建議措施的 Markdown 報告
```

---

## 前置需求

- Python 3.10+
- [Ollama](https://ollama.com/)，並下載一個**支援 tool calling** 的模型：
  ```bash
  ollama pull gemma4:e4b
  ```
  > gemma4/gemma3n 系列在 Ollama 的 OpenAI 相容 streaming tool_calls 上有已知回報問題（尤其是 system prompt ＋ tools 一起用時）。上課前務必用 `python check_env.py --llm` 實測，失敗就換備用模型：`ollama pull qwen2.5:7b`（或 `llama3.1:8b`）。
  > 現場若由講師架設共用推論伺服器，學員可省略安裝，改設 `OLLAMA_API_BASE` 即可。

---

## 快速開始（5 步）

以下指令以 Windows 為主；macOS 請把 `python` 換成 `python3`，把 `pip install ...` 換成 `python3 -m pip install ...`，並用 `source .venv/bin/activate` 啟動虛擬環境。

```bash
# 1. 建立並啟動虛擬環境，然後安裝套件
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 1.5 環境健檢（六項一次檢查，有 FAIL 會告訴你怎麼修）
python check_env.py

# 2. 產生合成日誌 → data/access_logs.json
python generate_logs.py

# 3.（可選）先不接 LLM，直接看工具輸出，確認資料 OK
python soc_agent/agent.py

# 4. 啟動 ADK 的對話 / 除錯介面
adk web

# 5. 瀏覽器開 http://localhost:8000 → 左上選 soc_agent → 開始用自然語言提問
```

預設連本機 Ollama（`http://localhost:11434/v1`）與 `gemma4:e4b`，本機跑就**不用改任何設定**。

---

## 現場同步講義（內網 live server）

上課時如果想讓學生看同一份網頁講義，並且你一修改、學生端就自動刷新，可以由講師電腦開一個內網 live server。

講師電腦先執行：

```bash
cd gdg-adk-demo
python3 live_server.py --host 0.0.0.0 --port 8008
```

查講師電腦的內網 IP：

```bash
ipconfig getifaddr en0
```

如果是有線網路，可能要改查：

```bash
ipconfig getifaddr en1
```

假設查到 `192.168.1.23`，學生就開：

```text
http://192.168.1.23:8008
```

`live_server.py` 會監看 `STUDENT_GUIDE.md`、`STUDENT_GUIDE_REVEAL.md`、`build_html.py` 和 `images/`。講師一存檔，它會自動重建對應的 HTML，已打開講義的瀏覽器會自動刷新。

這裡總共有兩個網頁：`http://講師IP:8008/`（或 `/STUDENT_GUIDE.html`）是學生從頭到尾看的主要講義，內容不含任何劇透；`http://講師IP:8008/STUDENT_GUIDE_REVEAL.html` 是另一份完全獨立的頁面，內容跟主講義一模一樣，只多了「第五間公司 Cyberdyne 其實被攻擊了」這段揭曉。想公布解答時，把揭曉頁的網址發給學生，或現場投影切過去即可，同樣會即時刷新。

注意：

- 講師和學生必須在同一個 Wi-Fi / LAN。
- macOS 防火牆跳出提示時，要允許 Python 接受連線。
- 有些學校 Wi-Fi 會開 AP isolation / client isolation，學生無法連到講師電腦；這時改用 `cloudflared tunnel --url http://localhost:8008` 或 `ngrok http 8008`。
- 上課前先用手機連同一個 Wi-Fi 測試 `http://講師IP:8008`。

---

## 設定（只有要覆寫預設時才需要）

用環境變數覆寫，或把 `.env.example` 複製成 `soc_agent/.env`：

| 變數 | 預設 | 說明 |
|---|---|---|
| `OLLAMA_API_BASE` | `http://localhost:11434/v1` | Ollama / 共用伺服器的 OpenAI 相容端點 |
| `OLLAMA_API_KEY`  | `ollama` | Ollama 不驗證，隨便填 |
| `OLLAMA_MODEL`    | `gemma4:e4b` | 要用的模型（需支援 tool calling；備用：`qwen2.5:7b` / `llama3.1:8b`） |

```bash
export OLLAMA_API_BASE="http://<講師伺服器>:11434/v1"
export OLLAMA_MODEL="gemma4:e4b"
```

---

## 試試這些提問

- 「這批 log 裡有哪些公司？」
- 「幫我把 log 分類，看看每家公司的風險。」
- 「分析 Initech 的資安狀況，寫一份報告。」
- 「Umbrella 有沒有被攻擊？」
- 「哪一家最危險？為什麼？」

---

## 專案結構

```
gdg-adk-demo/
├── generate_logs.py        # 產生合成日誌（含 4 種注入的攻擊行為）
├── requirements.txt
├── .env.example
├── data/
│   └── access_logs.json    # 執行 generate_logs.py 後產生
└── soc_agent/
    ├── __init__.py         # 讓 adk web 認得這個 agent 套件
    └── agent.py            # 工具 + 風險評分引擎 + root_agent
```

---

## 疑難排解

| 症狀 | 解法 |
|---|---|
| `adk web` 看不到 agent | 確認在 `gdg-adk-demo/` 目錄下執行，且 `soc_agent/__init__.py` 存在 |
| 找不到日誌資料 | 先跑 `python generate_logs.py` |
| 連線錯誤 / Connection refused | Ollama 沒開（`ollama serve`），或 `OLLAMA_API_BASE` 指錯 |
| Agent 不會呼叫工具 / 亂回答 | 模型不支援 tool calling，換 `qwen2.5:7b` 或 `llama3.1:8b` |

> ℹ️ 想比較不同模型，請優先換另一個本機模型，例如 `ollama pull qwen2.5:7b` 後把 `MODEL_NAME` 改成同一個模型名稱。資安日誌預設不送雲端。
