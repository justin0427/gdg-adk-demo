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
import subprocess
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


def _local_ollama_models():
    """用 `ollama list` 讀取本機實際已下載的模型名稱。"""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=8, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [line.split()[0] for line in result.stdout.splitlines()[1:] if line.split()]


def _model_is_installed(model, installed):
    """指定 tag 時精確比對；未指定 tag 時接受 Ollama 的 :latest。"""
    return model in installed or (":" not in model and f"{model}:latest" in installed)


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
    service_ok = False
    model_ok = False
    try:
        req = urllib.request.Request(BASE + "/models",
                                     headers={"Authorization": "Bearer " + API_KEY})
        with urllib.request.urlopen(req, timeout=4) as r:
            payload = json.load(r)
        models = [m.get("id", "") for m in payload.get("data", [])]
        service_ok = True
    except Exception:
        service_ok = False
    check(f"LLM 服務連線（{BASE}）", service_ok,
          "本機：開一個終端機執行 ollama serve；"
          "用共用伺服器：macOS/Linux 輸入 export OLLAMA_API_BASE=\"http://<講師給的網址>:11434/v1\"；"
          "Windows PowerShell 輸入 $env:OLLAMA_API_BASE = \"http://<講師給的網址>:11434/v1\""
          "（注意要寫 port，沒寫 port 預設會打到 80，連不到 Ollama）")

    # 本機直接以 `ollama list` 為準，避免把同家族的不同 tag 誤判為可用。
    if BASE in ("http://localhost:11434/v1", "http://127.0.0.1:11434/v1"):
        local_models = _local_ollama_models()
        if local_models is not None:
            models = local_models

    if service_ok:
        model_ok = _model_is_installed(MODEL, models)
        shown = ", ".join(models[:6]) or "（沒有找到已下載的模型）"
        check(f"模型 {MODEL}", model_ok,
              f"ollama pull {MODEL}（ollama list 顯示：{shown}）")

    # 6.（選配）實測 tool calling
    # 加上 system prompt 和 tools，貼近課堂 agent.py 的真實用法，
    # 直接以實測結果確認目前模型是否能正常完成 tool calling。
    if "--llm" in sys.argv and model_ok:
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
    elif "--llm" in sys.argv:
        check("模型支援 tool calling（含 system prompt）", False,
              "先修正上方的模型檢查，再重新執行 python check_env.py --llm")

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
