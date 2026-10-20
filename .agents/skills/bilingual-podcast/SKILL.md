---
name: bilingual-podcast
description: 每日雙語新聞 Podcast 產生器。抓取 BBC 國際新聞或中央社（CNA）、Yahoo 台灣新聞 RSS，支援「先英後中（外語聽力）」或「先中後英（學英文表達台灣時事）」雙向播報，搭配微軟 Edge Neural TTS 雙語主播合成高品質 MP3 音訊與雙語對照講稿。
---

# 每日雙語新聞 Podcast 產生器 Skill (bilingual-podcast)

本 Skill 提供全自動化新聞 Podcast 產製工作流，整合新聞 RSS 擷取、智慧雙語翻譯（含台灣用語在地化轉換）、微軟 Edge Neural TTS 高音質語音合成，以及 ffmpeg 音訊接合。

---

## 快速使用情境

使用者若提出以下需求，直接執行對應指令：

### 情境 1：台灣新聞學英文（先中文再英文）
> 範例：「幫我做今天台灣中央社新聞，中文先、英文後」
```powershell
uv run sound -s cna -n 5 --order zh-en --zh-voice yunzhe --en-voice aria
```
* **中文主播**：台灣男聲（雲哲 `zh-TW-YunJheNeural`）
* **英文主播**：美式女聲（Aria `en-US-AriaNeural`，新聞專用音）

---

### 情境 2：經典 BBC 聽力磨練（先英文再中文，預設）
> 範例：「幫我產今天的 BBC 雙語新聞」
```powershell
uv run sound -s bbc -n 8 --order en-zh --en-voice sonia --zh-voice yunzhe
```
* **英文主播**：英式女聲（Sonia `en-GB-SoniaNeural`，BBC 播報腔）
* **中文主播**：台灣男聲（雲哲 `zh-TW-YunJheNeural`）

---

### 情境 3：自選男女主播與風格搭檔
> 範例：「用曉臻（台灣女聲）和 Christopher（美式男聲）播報」
```powershell
uv run sound -s cna -n 6 --order zh-en --zh-voice xiaochen --en-voice christopher
```

---

## 參數說明

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

## 支援語音清單（Voice Aliases）

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

## 輸出結果

執行後自動於 `output/` 目錄產生兩個檔案：
1. **`.mp3`**：高品質 128kbps 立體聲廣播音訊，已接合背景段落停頓與 ID3 標籤。
2. **`.txt`**：逐字講稿，清楚標註每一段的語言、主播聲音 ID 與對照原文／譯文。
