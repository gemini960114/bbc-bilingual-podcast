"""通用每日雙語新聞 Podcast 產生器

支援多種新聞來源（BBC、中央社、Yahoo 等）、自訂播報順序（中英或英中）、
自訂男女主播語音（Microsoft Edge Neural TTS）與輸出雙語對照廣播。
"""

import argparse
import asyncio
import re
import sys
import tempfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

# 確保 Windows 控制台支援 UTF-8 與 Emoji 輸出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import edge_tts
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    from pydub import AudioSegment

# 內建新聞來源清單
PRESET_SOURCES = {
    "bbc": {
        "name": "BBC",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "lang": "en",
        "default_order": "en-zh",
    },
    "cna": {
        "name": "中央社 CNA",
        "url": "https://feeds.feedburner.com/cnaFirstNews",
        "lang": "zh",
        "default_order": "zh-en",
    },
    "yahoo": {
        "name": "Yahoo 台灣新聞",
        "url": "https://tw.news.yahoo.com/rss/",
        "lang": "zh",
        "default_order": "zh-en",
    },
}

# 常用語音別名對照表 (Microsoft Azure Neural TTS)
VOICE_ALIASES = {
    # 英文女聲
    "sonia": "en-GB-SoniaNeural",  # 英式女聲（BBC 經典）
    "libby": "en-GB-LibbyNeural",  # 英式女聲（明亮俐落）
    "aria": "en-US-AriaNeural",  # 美式女聲（新聞專用，知性自信）
    "jenny": "en-US-JennyNeural",  # 美式女聲（自然親切）
    # 英文男聲
    "ryan": "en-GB-RyanNeural",  # 英式男聲（英倫紳士）
    "thomas": "en-GB-ThomasNeural",  # 英式男聲（年輕自信）
    "christopher": "en-US-ChristopherNeural",  # 美式男聲（新聞專用，深沉權威）
    "guy": "en-US-GuyNeural",  # 美式男聲（熱情穩重）
    # 中文女聲
    "xiaochen": "zh-TW-HsiaoChenNeural",  # 台灣女聲（曉臻，溫柔專業）
    "xiaoyu": "zh-TW-HsiaoYuNeural",  # 台灣女聲（曉雨，清亮自然）
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",  # 大陸女聲（曉曉，新聞播報）
    # 中文男聲
    "yunzhe": "zh-TW-YunJheNeural",  # 台灣男聲（雲哲，親切沉穩）
    "yunyang": "zh-CN-YunyangNeural",  # 大陸男聲（雲揚，權威新聞主播）
}

FALLBACK_VOICES = {
    "zh-TW-YunJheNeural": "zh-CN-YunyangNeural",
    "zh-TW-HsiaoChenNeural": "zh-TW-HsiaoYuNeural",
    "zh-TW-HsiaoYuNeural": "zh-TW-HsiaoChenNeural",
}

# 譯名置換（將中國大陸譯名轉為台灣常見用語）
TW_TERMS = {
    "唐納德·特朗普": "唐納·川普",
    "特朗普": "川普",
    "內塔尼亞胡": "納坦雅胡",
    "澤連斯基": "澤倫斯基",
    "普京": "普丁",
    "英國廣播公司(BBC)": "BBC",
    "信息": "資訊",
    "視頻": "影片",
    "網絡": "網路",
    "軟件": "軟體",
    "人工智能": "人工智慧",
    "鏈接": "連結",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (daily-bilingual-podcast script)"}


def resolve_voice(voice: str) -> str:
    """支援縮寫別名（如 sonia, yunzhe, aria）或完整 Voice ID。"""
    return VOICE_ALIASES.get(voice.lower(), voice)


def fetch_headlines(source_key_or_url: str, limit: int, full: bool) -> tuple[str, str, list[dict]]:
    """抓取指定新聞來源的 RSS，回傳 (source_name, source_lang, items)。"""
    if source_key_or_url.lower() in PRESET_SOURCES:
        cfg = PRESET_SOURCES[source_key_or_url.lower()]
        name = cfg["name"]
        url = cfg["url"]
        lang = cfg["lang"]
    else:
        name = "新聞焦點"
        url = source_key_or_url
        lang = "en"

    resp = requests.get(url, headers=HEADERS, timeout=20)
    feed = feedparser.parse(resp.content)
    today = datetime.now(timezone.utc).date()

    entries = sorted(
        feed.entries,
        key=lambda e: e.get("published_parsed") or (0,) * 9,
        reverse=True,
    )

    # 優先篩選今日新聞，不足則取最新
    todays = [e for e in entries if e.get("published_parsed") and datetime(*e.published_parsed[:6]).date() == today]
    picked = (todays + [e for e in entries if e not in todays])[:limit]

    items = []
    for e in picked:
        clean_title = BeautifulSoup(e.title, "html.parser").get_text(strip=True)
        summary_raw = e.get("summary", "") or ""
        clean_summary = BeautifulSoup(summary_raw, "html.parser").get_text(strip=True)

        if lang == "en":
            punct = clean_title[-1] if clean_title and clean_title[-1] in ".?!" else "."
            title_text = clean_title + punct if clean_title and clean_title[-1] not in ".?!" else clean_title
            text = f"{title_text} {clean_summary}".strip()
            if full and hasattr(e, "link") and "bbc.co" in e.link:
                text += " " + fetch_lead(e.link)
            text = re.sub(r"\s*,\s*external\b", "", text)
        else:
            text = f"{clean_title}。{clean_summary}".strip()

        text = re.sub(r"\s+", " ", text).strip()
        items.append({"title": clean_title, "text": text, "link": getattr(e, "link", "")})

    return name, lang, items


def fetch_lead(url: str, paragraphs: int = 2) -> str:
    """從文章頁抓前幾段內文（主要針對 BBC）。"""
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select('[data-component="text-block"] p') or soup.select("article p")
    texts = [p.get_text(" ", strip=True) for p in blocks]
    return " ".join([t for t in texts if len(t) > 40][:paragraphs])


def chunk_sentences(text: str, max_len: int = 450) -> list[str]:
    """MyMemory 單次上限約 500 字元，按標點符號切段。"""
    chunks, current = [], ""
    parts = re.split(r"(?<=[.!?。！？])\s*", text)
    for part in parts:
        if not part:
            continue
        if current and len(current) + len(part) + 1 > max_len:
            chunks.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        chunks.append(current)
    return chunks


def translate_texts(texts: list[str], source_lang: str, target_lang: str) -> list[str]:
    """翻譯文字清單，優先使用 GoogleTranslator，失敗則退回 MyMemoryTranslator。"""
    src_map = {"en": "en", "zh": "zh-TW"}
    tgt_map = {"en": "en", "zh": "zh-TW"}
    mymemory_src = {"en": "en-GB", "zh": "zh-TW"}.get(source_lang, source_lang)
    mymemory_tgt = {"en": "en-GB", "zh": "zh-TW"}.get(target_lang, target_lang)

    try:
        translator = GoogleTranslator(source=src_map.get(source_lang, source_lang), target=tgt_map.get(target_lang, target_lang))
        results = []
        for t in texts:
            results.append(translator.translate(t))
            time.sleep(0.3)
        return results
    except Exception as exc:
        print(f"  Google 翻譯失敗（{type(exc).__name__}），改用 MyMemoryTranslator…")

    mymemory = MyMemoryTranslator(source=mymemory_src, target=mymemory_tgt)
    results = []
    for t in texts:
        chunks = chunk_sentences(t)
        translated_chunk = "".join(mymemory.translate(c) for c in chunks)
        results.append(translated_chunk)
    return results


def to_taiwan_terms(text: str) -> str:
    for cn, tw in TW_TERMS.items():
        text = text.replace(cn, tw)
    return text


async def synthesize(segments: list[tuple[str, str]], workdir: Path, rate: str, retries: int) -> list[Path]:
    """併發合成各段音訊，回傳依序排列的 mp3 檔路徑。"""
    sem = asyncio.Semaphore(4)

    async def one(i: int, voice: str, text: str) -> Path:
        path = workdir / f"{i:03d}.mp3"
        candidates = [voice] * retries + [FALLBACK_VOICES.get(voice, voice)] * 3
        async with sem:
            for attempt, v in enumerate(candidates, 1):
                try:
                    await edge_tts.Communicate(text, v, rate=rate).save(str(path))
                    if v != voice:
                        print(f"  第 {i} 段：{voice} 重試 {retries} 次仍失敗，已改用 {v}")
                    return path
                except edge_tts.exceptions.NoAudioReceived:
                    await asyncio.sleep(min(attempt, 3))
        raise RuntimeError(f"第 {i} 段語音合成失敗：{text[:30]}…")

    return await asyncio.gather(*(one(i, v, t) for i, (v, t) in enumerate(segments)))


def build_script(
    source_name: str,
    order: str,
    items: list[dict],
    translated_texts: list[str],
    en_voice: str,
    zh_voice: str,
) -> list[tuple[str, str]]:
    """建立雙語播報腳本序列。"""
    date_en = datetime.now().strftime("%A, %d %B %Y")
    now = datetime.now()
    date_zh = f"{now.year}年{now.month}月{now.day}日"
    count = len(items)

    segments: list[tuple[str, str]] = []

    if order == "en-zh":
        # 開場
        segments.append((en_voice, f"Good morning, this is your {source_name} daily briefing for {date_en}. Here are today's top {count} stories."))
        segments.append((zh_voice, f"大家早安，歡迎收聽 {source_name} 每日新聞雙語播報，今天是{date_zh}。以下是今天的{count}則頭條新聞。"))

        # 新聞主體
        for n, (item, zh_text) in enumerate(zip(items, translated_texts), 1):
            segments.append((en_voice, f"Story {n}. {item['text']}"))
            segments.append((zh_voice, f"第{n}則。{zh_text}"))

        # 結尾
        segments.append((en_voice, "That's all for today's briefing. Thanks for listening."))
        segments.append((zh_voice, "以上是今天的新聞播報，感謝您的收聽，我們明天見。"))

    else:  # zh-en
        # 開場
        segments.append((zh_voice, f"大家早安，歡迎收聽 {source_name} 每日新聞雙語播報，今天是{date_zh}。以下為您播報{count}則今日頭條焦點。"))
        segments.append((en_voice, f"Good morning, welcome to the {source_name} daily bilingual briefing for {date_en}. Here are today's top {count} stories."))

        # 新聞主體
        for n, (item, en_text) in enumerate(zip(items, translated_texts), 1):
            segments.append((zh_voice, f"第{n}則。{item['text']}"))
            segments.append((en_voice, f"Story {n}. {en_text}"))

        # 結尾
        segments.append((zh_voice, "以上是今天的新聞播報，感謝您的收聽，我們明天見。"))
        segments.append((en_voice, "That concludes today's news briefing. Thank you for listening, and have a great day."))

    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description="通用每日雙語新聞 Podcast 產生器")
    parser.add_argument("-s", "--source", default="bbc", help="新聞來源：bbc、cna（中央社）、yahoo 或 自訂 RSS 網址（預設 bbc）")
    parser.add_argument("--order", choices=["en-zh", "zh-en"], help="播報順序：en-zh (先英後中) 或 zh-en (先中後英，適合台灣新聞學英文)")
    parser.add_argument("--en-voice", default="en-GB-SoniaNeural", help="英文聲音，可填別名（sonia, aria, christopher, ryan, jenny）或完整 Voice ID")
    parser.add_argument("--zh-voice", default="zh-TW-YunJheNeural", help="中文聲音，可填別名（yunzhe, xiaochen, xiaoyu, yunyang）或完整 Voice ID")
    parser.add_argument("-n", "--limit", type=int, default=6, help="新聞則數（預設 6）")
    parser.add_argument("--full", action="store_true", help="針對 BBC 另外抓取文章前段內文")
    parser.add_argument("--rate", default="+0%", help="語速，例如 +10% 或 -5%")
    parser.add_argument("--pause", type=int, default=600, help="段落間停頓毫秒數（預設 600）")
    parser.add_argument("--retries", type=int, default=12, help="語音合成重試次數（預設 12）")
    parser.add_argument("-o", "--output", type=Path, help="輸出 mp3 路徑（預設 output/{source}_{YYYYMMDD}.mp3）")
    args = parser.parse_args()

    en_voice = resolve_voice(args.en_voice)
    zh_voice = resolve_voice(args.zh_voice)

    source_key = args.source.lower()
    source_name, source_lang, items = fetch_headlines(args.source, args.limit, args.full)
    if not items:
        print("未抓取到任何新聞項目，請檢查新聞來源網址。")
        return

    # 決定播報順序
    if args.order:
        order = args.order
    elif source_key in PRESET_SOURCES:
        order = PRESET_SOURCES[source_key]["default_order"]
    else:
        order = "en-zh" if source_lang == "en" else "zh-en"

    default_filename = f"{source_key if source_key in PRESET_SOURCES else 'news'}_{datetime.now():%Y%m%d}.mp3"
    output = args.output or Path("output") / default_filename
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"📡 抓取 {source_name} 今日新聞（共 {len(items)} 則）…")
    for n, item in enumerate(items, 1):
        print(f"  {n}. {item['title']}")

    if order == "en-zh":
        print("🌐 英文原文 ➔ 翻譯為台灣繁體中文…")
        translated_texts = [to_taiwan_terms(t) for t in translate_texts([it["text"] for it in items], source_lang="en", target_lang="zh")]
    else:
        print("🌐 中文原文 ➔ 翻譯為英文講稿…")
        translated_texts = translate_texts([it["text"] for it in items], source_lang="zh", target_lang="en")

    segments = build_script(
        source_name=source_name,
        order=order,
        items=items,
        translated_texts=translated_texts,
        en_voice=en_voice,
        zh_voice=zh_voice,
    )

    # 輸出文字講稿
    txt_path = output.with_suffix(".txt")
    script_lines = []
    for voice, text in segments:
        lang_tag = "EN" if "en-" in voice else "ZH"
        script_lines.append(f"[{lang_tag} - {voice}] {text}")
    txt_path.write_text("\n\n".join(script_lines), encoding="utf-8")

    print(f"🎙️ 合成 {len(segments)} 段雙語語音（英文音色: {en_voice}，中文音色: {zh_voice}）…")
    with tempfile.TemporaryDirectory() as tmp:
        paths = asyncio.run(synthesize(segments, Path(tmp), args.rate, args.retries))
        gap = AudioSegment.silent(duration=args.pause)
        podcast = AudioSegment.empty()
        for p in paths:
            podcast += AudioSegment.from_mp3(p) + gap
        podcast.export(
            output,
            format="mp3",
            bitrate="128k",
            tags={"title": f"{source_name} 每日雙語播報 {datetime.now():%Y-%m-%d}"},
        )

    print(f"🎉 產製完成！")
    print(f"  • 音訊檔案：{output}（時長：{len(podcast) / 60000:.1f} 分鐘）")
    print(f"  • 逐字講稿：{txt_path}")


if __name__ == "__main__":
    main()
