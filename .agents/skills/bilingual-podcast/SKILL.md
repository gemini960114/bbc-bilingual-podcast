---
name: bilingual-podcast
description: 每日雙語新聞 Podcast 產生器。抓取 BBC 國際新聞或中央社（CNA）、Yahoo 台灣新聞 RSS，支援「先英後中（外語聽力）」或「先中後英（學英文表達台灣時事）」雙向播報，搭配微軟 Edge Neural TTS 雙語主播合成高品質 MP3 音訊與雙語對照講稿。
---

# 每日雙語新聞 Podcast 產生器 Skill (bilingual-podcast)

本 Skill 為**自包含獨立（Portable & Self-Contained）下載包**，可放置於任何目錄或全域 Skill 目錄。內部 Python 腳本內嵌 PEP 723 依賴宣告，執行時由 `uv` 自動在專屬隔離沙盒中運行，**絕不污染全域環境，也不會與其他專案套件衝突**。

---

## 零、 環境需求確認（唯一外部依賴）

執行本 Skill 前，請確保系統已安裝音訊底層工具 `ffmpeg`：
```powershell
ffmpeg -version
```
* **若未安裝**：
  * **Windows**：執行 `winget install Gyan.FFmpeg`
  * **macOS**：執行 `brew install ffmpeg`
  * **Linux (Ubuntu/Debian)**：執行 `sudo apt update && sudo apt install -y ffmpeg`

*(註：Python 套件不需要手動安裝，`uv run` 會依腳本內嵌宣告自動沙盒化即時載入)*

---

## 壹、 執行方式

本 Skill 支援以下兩種執行方式：

### 方式 A：在任何專案目錄直接調用本 Skill 的獨立腳本（推薦）
```powershell
uv run .agents/skills/bilingual-podcast/scripts/podcast.py [參數]
# 若此 Skill 安裝在全域目錄（~/.gemini/config/skills/bilingual-podcast/）：
# uv run "$HOME/.gemini/config/skills/bilingual-podcast/scripts/podcast.py" [參數]
```

### 方式 B：在本專案環境中執行 CLI
```powershell
uv run sound [參數]
```

---

## 貳、 快速使用情境

使用者提出需求時，直接依情境執行對應指令：

### 情境 1：台灣新聞學英文（先中文再英文）
> 範例：「幫我做今天台灣中央社新聞，中文先、英文後」
```powershell
uv run .agents/skills/bilingual-podcast/scripts/podcast.py -s cna -n 5 --order zh-en --zh-voice yunzhe --en-voice aria
```
* **中文主播**：台灣男聲（雲哲 `zh-TW-YunJheNeural`）
* **英文主播**：美式女聲（Aria `en-US-AriaNeural`，新聞專用音）

---

### 情境 2：經典 BBC 聽力磨練（先英文再中文，預設）
> 範例：「幫我產今天的 BBC 雙語新聞」
```powershell
uv run .agents/skills/bilingual-podcast/scripts/podcast.py -s bbc -n 8 --order en-zh --en-voice sonia --zh-voice yunzhe
```
* **英文主播**：英式女聲（Sonia `en-GB-SoniaNeural`，BBC 播報腔）
* **中文主播**：台灣男聲（雲哲 `zh-TW-YunJheNeural`）

---

### 情境 3：自選男女主播與風格搭檔
> 範例：「用曉臻（台灣女聲）和 Christopher（美式男聲）播報 6 則中央社要聞」
```powershell
uv run .agents/skills/bilingual-podcast/scripts/podcast.py -s cna -n 6 --order zh-en --zh-voice xiaochen --en-voice christopher
```

---

## 參、 參數說明

| 參數 | 縮寫 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `--source` | `-s` | `bbc` | 新聞來源：`bbc`、`cna`（中央社）、`yahoo` 或自訂 RSS 網址 |
| `--order` | | 自動判定 | 播報順序：`zh-en`（先中後英）或 `en-zh`（先英後中） |
| `--zh-voice` | | `yunzhe` | 中文主播語音（可填別名或完整 Voice ID） |
| `--en-voice` | | `sonia` | 英文主播語音（可填別名或完整 Voice ID） |
| `--limit` | `-n` | `6` | 抓取新聞頭條則數 |
| `--full` | | 關閉 | 針對 BBC 抓取新聞前段內文（加長每則內容） |
| `--rate` | | `+0%` | 播報語速調整，例如 `+10%`、`-5%` |
| `--pause` | | `600` | 段落間隔靜音長度（毫秒） |
| `--output` | `-o` | 自動 | 輸出路徑（預設 `output/{source}_{YYYYMMDD}.mp3`） |

---

## 肆、 支援語音清單（Voice Aliases）

### 台灣繁體中文 (zh-TW)
- `yunzhe`：`zh-TW-YunJheNeural`（男聲，親切自然沉穩）
- `xiaochen`：`zh-TW-HsiaoChenNeural`（女聲，溫柔知性標準主播）
- `xiaoyu`：`zh-TW-HsiaoYuNeural`（女聲，清亮俐落活力）
- `yunyang`：`zh-CN-YunyangNeural`（男聲，新聞主播音，備援使用）

### 英文 (en-GB / en-US)
- `sonia`：`en-GB-SoniaNeural`（英式女聲，BBC 經典聽力播報）
- `ryan`：`en-GB-RyanNeural`（英式男聲，紳士知性）
- `aria`：`en-US-AriaNeural`（美式女聲，專業權威新聞播音員）
- `christopher`：`en-US-ChristopherNeural`（美式男聲，深沉厚實新聞音）
- `jenny`：`en-US-JennyNeural`（美式女聲，生活親切自然）

---

## 伍、 輸出結果

執行後自動於工作目錄之 `output/` 產出：
1. **`.mp3`**：高品質 128kbps 立體聲廣播音訊，已接合背景段落停頓與 ID3 標籤。
2. **`.txt`**：逐字講稿，清楚標註每一段的語言、主播聲音 ID 與對照原文／譯文。
