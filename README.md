# 每日雙語新聞 Podcast 產生器 (Bilingual News Podcast)

支援抓取國際頭條（BBC）或台灣焦點新聞（中央社 CNA、Yahoo），雙主播輪流播報，自動輸出 MP3 廣播與逐字講稿。

支援 **雙向播報模式**：
- **先英後中 (`en-zh`)**：BBC 國際新聞聽力磨練，英式女聲朗讀原文，接著台灣男聲繁體中文解說。
- **先中後英 (`zh-en`)**：台灣時事新聞學英語，先聽懂台灣新聞脈絡，接著學習如何以標準英語向國際表達。

---

## 快速執行

```powershell
# 1. 預設模式：BBC 雙語新聞（先英後中）
uv run sound

# 2. 台灣新聞學英語：抓中央社 CNA，先中文後英文（曉臻台灣女聲 + Aria 美式女聲）
uv run sound -s cna --order zh-en --zh-voice xiaochen --en-voice aria

# 3. 指定則數與抓取內文
uv run sound -n 5 --full

# 4. 微調語速與段落停頓
uv run sound --rate +10% --pause 800 -o output/today.mp3
```

> **環境需求**：系統需安裝 `ffmpeg`（供音訊切合使用）。

---

## 常用參數

| 參數 | 預設值 | 說明 |
| :--- | :--- | :--- |
| `-s, --source` | `bbc` | 新聞來源：`bbc`、`cna`（中央社）、`yahoo` 或 自訂 RSS 網址 |
| `--order` | 自動 | 播報順序：`en-zh`（先英後中）或 `zh-en`（先中後英） |
| `--zh-voice` | `yunzhe` | 中文主播音色（可填別名或完整 Voice ID） |
| `--en-voice` | `sonia` | 英文主播音色（可填別名或完整 Voice ID） |
| `-n, --limit` | `6` | 抓取頭條則數 |
| `--full` | 關閉 | 抓取文章前段內文（加長內容，BBC 適用） |
| `--rate` | `+0%` | 語速調整（如 `+10%`、`-5%`） |
| `--pause` | `600` | 段落間隔停頓時間（毫秒） |
| `-o, --output` | 自動 | 指定輸出音訊路徑（預設 `output/{source}_{YYYYMMDD}.mp3`） |

---

## 推薦主播聲音

### 台灣繁體中文 (zh-TW)
- **`yunzhe`**（雲哲，男聲）：`zh-TW-YunJheNeural` - 沉穩自然親切
- **`xiaochen`**（曉臻，女聲）：`zh-TW-HsiaoChenNeural` - 溫和標準專業主播
- **`xiaoyu`**（曉雨，女聲）：`zh-TW-HsiaoYuNeural` - 清新自然活力

### 英語 (en-GB / en-US)
- **`sonia`**（英式女聲）：`en-GB-SoniaNeural` - 經典 BBC 播報腔
- **`aria`**（美式女聲）：`en-US-AriaNeural` - 專業新聞專用音
- **`christopher`**（美式男聲）：`en-US-ChristopherNeural` - 磁性厚實新聞主播
- **`ryan`**（英式男聲）：`en-GB-RyanNeural` - 英倫紳士知性音

---

## 流程架構

1. **新聞擷取**：RSS 即時抓取今日最新要聞
2. **智慧翻譯**：Google 翻譯 ➔ 若受限自動切換 MyMemory，並將用語在地化為台灣用語（`TW_TERMS`）
3. **雲端語音**：微軟 Edge Neural TTS 雙語即時串流合成（附自動失敗重試與備援聲音）
4. **廣播混音**：`pydub` 接合音訊、加入自然呼吸停頓，同時輸出 `.mp3` 與雙語逐字 `.txt` 講稿
