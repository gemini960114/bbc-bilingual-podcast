# BBC 每日雙語新聞 Podcast

抓取 BBC News 本日頭條，女聲（英式英語）播報一則，男聲接著用台灣繁體中文播報同一則，輪流進行，輸出 mp3 與講稿。

## 執行

```powershell
uv run sound                 # 預設 8 則，輸出 output/bbc_YYYYMMDD.mp3
uv run sound -n 5 --full     # 5 則，並抓文章前兩段內文
uv run sound --rate +10% --pause 800 -o today.mp3
```

需要 ffmpeg（pydub 用來接合音訊）。

## 流程

1. RSS：`feeds.bbci.co.uk/news/rss.xml`，優先取今天發布的新聞，不足時以最新新聞補齊
2. 翻譯：Google 翻譯 → 若被限流改用 MyMemory，並把中國大陸譯名換成台灣用語（`TW_TERMS`）
3. 語音：edge-tts，女聲 `en-GB-SoniaNeural`、男聲 `zh-TW-YunJheNeural`
4. 用 pydub 接合各段並加入停頓，輸出 mp3 與 `.txt` 講稿

`zh-TW-YunJheNeural` 的服務端不穩，常回 `NoAudioReceived`；程式會重試（`--retries`），仍失敗才改用 `zh-CN-YunyangNeural`。
