<p align="center"><img src="images/gdgc-logo.svg" alt="Google Developer Groups On Campus" width="400" class="logo-light"><img src="images/gdgc-logo-dark.svg" alt="Google Developer Groups On Campus" width="400" class="logo-dark"></p>

# 上課前置作業：先把環境準備好

這是「用 Google ADK ＋ 地端 LLM 打造你的第一支 AI Agent」這堂課的行前準備，請務必在上課前完成——尤其是下載模型那一步，現場網路撐不住幾十人同時下載。整個流程大約 10 到 15 分鐘，另外加上模型下載的時間，看你家裡的網速。

做完這份前置作業，你會有：一個裝好課程套件的乾淨 Python 環境、一個能在自己電腦上跑的 AI 模型（不用申請任何帳號、不用付費 API），以及一份可以重跑的健檢清單，確認一切就緒。

---

## 你需要準備

- 一台可以安裝軟體的筆電（Windows 或 macOS 都可以）
- 家裡或穩定的網路（要下載一個約 9.6GB 的模型檔）
- 大約 15 分鐘 + 下載等待時間

---

## 步驟 1：安裝 Python

需要 Python 3.10 以上。macOS 有些版本已經內建，也可以到 [python.org](https://www.python.org/downloads/) 下載安裝；Windows 一樣去官網下載，安裝時記得勾選「Add python.exe to PATH」。

```bash 終端機
python --version
```

確認一下：看到的版本號是 3.10 以上，代表這一步完成了。

如果出問題：如果指令找不到（`command not found` 或 `不是內部或外部命令`），代表安裝時沒有把 Python 加進系統路徑，重新安裝一次、記得勾選加入 PATH 的選項。

---

## 步驟 2：安裝 Ollama、下載模型（最花時間，請現在就做）

[Ollama](https://ollama.com/) 是讓你在自己電腦上跑 AI 模型的工具，到 [ollama.com/download](https://ollama.com/download) 下載安裝——用上面的切換鈕選你的作業系統，看對應的安裝步驟：

::: mac
需要 macOS 14（Sonoma）以上。下載下來是一個 `.dmg` 檔，打開它會跳出一個磁碟視窗，把裡面的 `Ollama.app` 拖進「應用程式」（Applications）資料夾，再打開它。第一次開啟可能會跳出視窗要求把命令列工具連結加進系統路徑，按同意即可；選單列（畫面最上方）會出現一個小圖示，代表 Ollama 已經在背景執行。
:::

::: windows
下載下來是 `OllamaSetup.exe`，雙擊執行，照畫面指示一路「下一步」安裝完成——不需要系統管理員權限，學校電腦也能裝。它會自動把 `ollama` 加進使用者的系統路徑，並在背景執行（工作列會有圖示）。**安裝完後請重新開一個新的終端機視窗**，路徑設定才會生效；如果安裝過程跳出 Windows 防火牆詢問，選「允許」即可。
:::

裝好後在終端機打 `ollama --version` 應該會看到版本號，代表裝好了。接著執行：

```bash 終端機
ollama pull gemma4:e4b
```

這個模型大約 9.6GB，麻煩趁現在網路好的時候（例如在家裡）先下載完成。現場如果大家一起下載，網路很容易撐不住，你會卡在這一步乾等，錯過後面實際動手的時間。

如果出問題：`ollama` 指令找不到，通常是安裝後沒有重開終端機（Windows 常見），關掉重開一個試試；下載很慢或中斷，換一個網路環境（例如家裡的 Wi-Fi）重試一次；真的裝不起來也沒關係，提早 15 分鐘到現場，我可以協助你改連共用伺服器，不用自己的模型也能上課。

---

## 步驟 3：下載課程專案

點這個連結直接下載 zip：[gdg-adk-demo.zip](https://github.com/justin0427/gdg-adk-demo/archive/refs/heads/main.zip)。

下載後解壓縮，資料夾名稱會是 `gdg-adk-demo-main`，用終端機切換進去——之後的指令都要在這個資料夾裡執行（資料夾名稱不影響操作，不用特別改名）。

---

## 步驟 4：建立虛擬環境、安裝套件

```bash 終端機
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

確認一下：指令跑完後，終端機最前面會出現 `(.venv)` 字樣，代表你已經進入這個專案專用的乾淨環境，之後裝的套件都不會影響到你電腦上其他專案。

如果出問題：出現 `externally-managed-environment` 這個錯誤訊息，代表你忘了先執行第二行啟動虛擬環境，回到這一步重新照順序跑一次。

---

## 步驟 5：跑健檢，確認萬事俱備

```bash 終端機
python check_env.py
```

你會看到六項檢查結果。這時候「示範資料」那一項顯示 `[FAIL]` 是正常的——那份資料要留到上課當天現場產生，先不用管它；其他五項都應該是 `[OK]`。

如果出問題：每個 `[FAIL]` 底下都會印出對應的修法，照做即可。如果是「模型」或「LLM 服務連線」沒過，先確認 Ollama 有沒有在背景執行（有些系統安裝完會自動啟動；沒有的話手動執行 `ollama serve`），再用 `ollama list` 確認 `gemma4:e4b` 真的下載完成了。

想更確定模型能正常配合這堂課的用法（不是必要，但建議做），可以多跑一次：

```bash 終端機
python check_env.py --llm
```

這會實際呼叫一次模型，測試它會不會正確執行工具呼叫。第一次執行模型需要載入，可能要等一下，屬於正常現象。

---

## 前置作業檢查清單

全部完成後，你應該可以打勾以下項目：

- [ ] Python 3.10 以上已安裝
- [ ] Ollama 已安裝，`gemma4:e4b` 已下載完成
- [ ] 課程專案已下載，虛擬環境已建立並啟動（終端機前面看得到 `(.venv)`）
- [ ] `pip install -r requirements.txt` 執行成功
- [ ] `python check_env.py` 除了「示範資料」以外，其他都是 `[OK]`

全部打勾，你就準備好了，上課當天直接帶筆電來就可以開始動手做。

如果卡在任何一步都沒關係——把畫面截圖下來，提早 15 分鐘到現場，我會幫你處理，不會耽誤到你上課。
