"""
check_env.py — 課前 / 課中環境健檢：一個指令確認你能順利跟完整堂課。

用法：
  python check_env.py          基本健檢（六項，幾秒內跑完）
  python check_env.py --llm    加測「模型是否真的支援 tool calling」（會實際呼叫模型，較慢）

環境變數（用共用伺服器時才需要設）：
  OLLAMA_API_BASE   預設 http://localhost:11434/v1
  OLLAMA_MODEL      預設 gemma4:e4b
"""

import importlib
import json
import os
import shutil
import sys
import urllib.request

BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1").rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
HERE = os.path.dirname(os.path.abspath(__file__))

_results = []


def check(name, ok, fix=""):
    _results.append(ok)
    print(("[OK]  " if ok else "[FAIL]") + " " + name)
    if not ok and fix:
        print("       修法：" + fix)
    return ok


def main():
    print(f"環境健檢　endpoint={BASE}　model={MODEL}")
    print("-" * 56)

    # 1. Python 版本
    check(f"Python 版本 {sys.version.split()[0]}（需 3.10 以上）",
          sys.version_info >= (3, 10),
          "請安裝 Python 3.10 以上，再重新建立虛擬環境")

    # 2. 套件
    for module, pip_name in [("google.adk", "google-adk"), ("litellm", "litellm")]:
        try:
            importlib.import_module(module)
            ok = True
        except Exception:
            ok = False
        check(f"套件 {pip_name}", ok, f"pip install {pip_name}")

    # 3. adk 指令
    adk_here = os.path.join(os.path.dirname(sys.executable), "adk")
    check("adk 指令可用",
          bool(shutil.which("adk")) or os.path.exists(adk_here),
          "pip install google-adk，並確認虛擬環境已啟用")

    # 4. 示範資料
    data_path = os.path.join(HERE, "data", "access_logs.json")
    n = 0
    if os.path.exists(data_path):
        try:
            with open(data_path, encoding="utf-8") as f:
                n = len(json.load(f))
        except Exception:
            n = 0
    check(f"示範資料 data/access_logs.json（{n} 筆）", n > 0,
          "python generate_logs.py（這是課程關卡 1，還沒上到很正常）")

    # 5. LLM 服務連線 + 模型
    models = []
    try:
        req = urllib.request.Request(BASE + "/models",
                                     headers={"Authorization": "Bearer " + API_KEY})
        with urllib.request.urlopen(req, timeout=4) as r:
            payload = json.load(r)
        models = [m.get("id", "") for m in payload.get("data", [])]
        ok = True
    except Exception:
        ok = False
    check(f"LLM 服務連線（{BASE}）", ok,
          "本機：開一個終端機執行 ollama serve；"
          "用共用伺服器：export OLLAMA_API_BASE=\"http://<講師給的網址>:11434/v1\""
          "（注意要寫 port，沒寫 port 預設會打到 80，連不到 Ollama）")

    if models:
        family = MODEL.split(":")[0].lower()
        found = any(m == MODEL or m.startswith(MODEL) or family in m.lower() for m in models)
        shown = ", ".join(models[:6]) or "（伺服器上沒有任何模型）"
        check(f"模型 {MODEL}", found, f"ollama pull {MODEL}（目前伺服器上有：{shown}）")

        known_good = ("qwen", "llama3", "mistral", "gpt-oss", "hermes", "command-r")
        risky = ("gemma4", "gemma3n", "gemma3")
        if found and family in risky:
            print(f"[WARN] {family} 系列在 Ollama 的 OpenAI 相容 streaming tool_calls 上有已知回報問題"
                  "（尤其是「system prompt ＋ tools 一起用」時，這正是這堂課的用法）。"
                  "務必用 --llm 實測，失敗就換 qwen2.5:7b 或 llama3.1:8b：ollama pull qwen2.5:7b")
        elif found and not any(k in family for k in known_good):
            print("[WARN] 這個模型不一定支援 tool calling，課堂建議 qwen2.5:7b 或 llama3.1:8b")

    # 6.（選配）實測 tool calling
    # 特意加了 system prompt，重現「system prompt ＋ tools」這個已知較容易出問題的組合，
    # 貼近課堂 agent.py 的真實用法（SYSTEM_INSTRUCTION ＋ 三個工具），不能只用單純 user 訊息測。
    if "--llm" in sys.argv and models:
        print("-" * 56)
        print("實測 tool calling（模擬「system prompt + tools」的真實課堂用法，第一次可能要載入模型，請稍候）...")
        body = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "你是一個會呼叫工具的助手。"},
                {"role": "user", "content": "請呼叫工具查現在時間"},
            ],
            "tools": [{
                "type": "function",
                "function": {"name": "get_time", "description": "取得現在時間",
                             "parameters": {"type": "object", "properties": {}}},
            }],
        }
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + API_KEY})
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.load(r)
            msg = resp.get("choices", [{}])[0].get("message", {})
            calls = msg.get("tool_calls")
            leaked = not calls and any(tag in (msg.get("content") or "")
                                       for tag in ("tool_call", "<|", "function_call"))
            check("模型支援 tool calling（含 system prompt）", bool(calls),
                  "換成 qwen2.5:7b 或 llama3.1:8b（ollama pull qwen2.5:7b）"
                  + ("；偵測到疑似特殊 token 洩漏到回覆內容，符合已知 gemma4/gemma3n 的解析錯誤"
                     if leaked else ""))
        except Exception as e:
            check("模型支援 tool calling（含 system prompt）", False, f"呼叫失敗：{e}")

    # 總結
    print("-" * 56)
    passed, total = sum(_results), len(_results)
    if passed == total:
        print(f"全部通過（{passed}/{total}），可以上課了。")
    else:
        print(f"通過 {passed}/{total}，請照上面的「修法」處理；"
              "模型相關項目沒過也沒關係，關卡 1 到 3 用不到模型。")
        sys.exit(1)


if __name__ == "__main__":
    main()
