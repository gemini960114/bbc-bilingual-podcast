# 實作案例：雙語新聞 Podcast 產生器（Skill 封裝）

---

## 1. 提出需求：雙語新聞聽力 Podcast

### 需求目標
- 想練習英文聽力與時事表達，需要雙語輪流播報的 Podcast。
- 支援兩種模式：
  - **BBC 國際新聞**：先英後中（外語聽力磨練）。
  - **台灣在地新聞**：先中後英（學如何用英文聊台灣焦點）。

### 當時下的 Prompt
> 「我想練習英文聽力，幫我做一個雙語新聞 Podcast：抓取本日頭條，一段英文、一段台灣繁體中文輪流播報，輸出成 mp3 和逐字講稿。」

### 產出
- 抓取 RSS 來源（BBC / 中央社）。
- 翻譯對照並置換台灣用語。
- 串接微軟 Edge TTS 與 ffmpeg 接合音訊。

---

## 2. 多輪測試：語氣切換與釐清技術底層

### 測試與調整
- 測試男女聲搭配（台灣腔男聲/女聲、英音女聲、美音男/女聲）。
- 測試語言播報順序（先英後中 vs 先中後英）。
- 追問底層技術，確認沒有偷用收費 API 或在本地裝龐大模型。

### 當時下的 Prompt
> 「你用了哪些 TTS model？是用 Gemini Flash 3.8 嗎？」  
> 「你可以用 Gemini 做 TTS 嗎？那我要在電腦安裝微軟什麼模型？」  
> 「男女生也可以指定嗎？先給我建議選擇，不然我也不知道有哪些聲音。」

### 釐清結果
- **TTS 來源**：使用的是微軟 Edge Neural TTS 線上服務，免 API Key、完全免費。
- **免裝模型**：音訊在雲端即時合成串流回傳，電腦不需要下載任何模型檔案。

---

## 3. 規格加碼：做成獨立 Skill 與套件依賴防護

### 考量重點
- 把腳本從「專案專用」升級為「通用 Agent Skill」。
- 考量其他人下載 Skill 時，避免 `pip install` 污染對方的電腦或和其他專案套件衝突。

### 當時下的 Prompt
> 「這個適合寫成一個 Skill 嗎？但要能通用，比如台灣新聞中文先說、再翻成英文，男女聲也可以指定。」  
> 「那我 Skill 要附上這些說明或者直接提供套件安裝，確保大家都一致？」  
> 「我的意思是，如果我只提供 Skill 下載包可以嗎？會不會裝到別的套件？用沙盒是個好方案嗎還是更麻煩？」

### 解決方案
- 腳本頂部加入 PEP 723 內嵌依賴宣告。
- 使用 `uv run podcast.py` 執行，自動在隔離沙盒跑，不碰使用者的全域 Python。

---

## 4. 完成 Skill、測試與上架

### 交付清單
- **腳本**：`scripts/podcast.py`（自帶依賴宣告，單檔隨處可跑）。
- **說明**：`SKILL.md`（定義參數、聲音別名與前置檢查）。
- **全域部署**：安裝至 `~/.gemini/config/skills/bilingual-podcast/`。
- **Git 倉庫**：建立並推送到 GitHub `gemini960114/bbc-bilingual-podcast`。

### 當時下的 Prompt
> 「請製作。」  
> 「幫我建立一個 repo 幫我取名 然後 commit push」

### 驗證指令
```powershell
uv run .agents/skills/bilingual-podcast/scripts/podcast.py -s cna -n 2 --order zh-en --zh-voice xiaochen --en-voice aria
```
* **結果**：成功輸出 2.4 分鐘 MP3 廣播與逐字講稿 TXT。
