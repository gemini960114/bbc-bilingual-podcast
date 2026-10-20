"""BBC 每日新聞頭條 podcast：女聲英文播報一段，男聲接著用台灣繁體中文播報同一段，輪流進行。"""

import argparse
import asyncio
import re
import tempfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import edge_tts
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    from pydub import AudioSegment

RSS_URL = "https://feeds.bbci.co.uk/news/rss.xml"
FEMALE_VOICE = "en-GB-SoniaNeural"  # 英式英語女聲
MALE_VOICE = "zh-TW-YunJheNeural"  # 台灣國語男聲
FALLBACK_VOICES = {MALE_VOICE: "zh-CN-YunyangNeural"}  # 新聞主播男聲，口音偏中國大陸
# MyMemory 常用中國大陸譯名，換成台灣用語
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
}
HEADERS = {"User-Agent": "Mozilla/5.0 (daily-podcast script)"}


def fetch_headlines(limit: int, full: bool) -> list[dict]:
    """抓 BBC RSS，優先取今天（UTC）發布的新聞，不足時以最新新聞補齊。"""
    feed = feedparser.parse(requests.get(RSS_URL, headers=HEADERS, timeout=20).content)
    today = datetime.now(timezone.utc).date()

    entries = sorted(
        feed.entries,
        key=lambda e: e.get("published_parsed") or (0,) * 9,
        reverse=True,
    )
    todays = [e for e in entries if e.get("published_parsed") and datetime(*e.published_parsed[:6]).date() == today]
    picked = (todays + [e for e in entries if e not in todays])[:limit]

    items = []
    for e in picked:
        title = e.title if e.title[-1] in ".?!" else e.title + "."
        text = f"{title} {e.get('summary', '')}"
        if full:
            text += " " + fetch_lead(e.link)
        text = re.sub(r"\s*,\s*external\b", "", text)  # BBC 外部連結標記
        items.append({"title": e.title, "text": re.sub(r"\s+", " ", text).strip(), "link": e.link})
    return items


def fetch_lead(url: str, paragraphs: int = 2) -> str:
    """從文章頁抓前幾段內文，失敗就回傳空字串。"""
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select('[data-component="text-block"] p') or soup.select("article p")
    texts = [p.get_text(" ", strip=True) for p in blocks]
    return " ".join([t for t in texts if len(t) > 40][:paragraphs])


def chunk_sentences(text: str, max_len: int = 450) -> list[str]:
    """MyMemory 單次上限 500 字元，按句子切段。"""
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) + 1 > max_len:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    return chunks + [current] if current else chunks


def translate(texts: list[str]) -> list[str]:
    """先用 Google 翻譯；若被限流（IP 被擋時常見）改用 MyMemory。"""
    try:
        google = GoogleTranslator(source="en", target="zh-TW")
        results = []
        for t in texts:
            results.append(google.translate(t))
            time.sleep(0.3)
        return results
    except Exception as exc:
        print(f"  Google 翻譯失敗（{type(exc).__name__}），改用 MyMemory")

    mymemory = MyMemoryTranslator(source="en-GB", target="zh-TW")
    return ["".join(mymemory.translate(c) for c in chunk_sentences(t)) for t in texts]


def to_taiwan_terms(text: str) -> str:
    for cn, tw in TW_TERMS.items():
        text = text.replace(cn, tw)
    return text


async def synthesize(segments: list[tuple[str, str]], workdir: Path, rate: str, retries: int) -> list[Path]:
    """segments 為 (voice, text)；併發合成，回傳依序排列的 mp3 檔路徑。

    zh-TW-YunJheNeural 服務端不穩，常回 NoAudioReceived，所以重試後再退回備用聲音。
    """
    sem = asyncio.Semaphore(4)

    async def one(i: int, voice: str, text: str) -> Path:
        path = workdir / f"{i:03d}.mp3"
        candidates = [voice] * retries + [FALLBACK_VOICES.get(voice, voice)] * 3
        async with sem:
            for attempt, v in enumerate(candidates, 1):
                try:
                    await edge_tts.Communicate(text, v, rate=rate).save(str(path))
                    if v != voice:
                        print(f"  第 {i} 段：{voice} 重試 {retries} 次仍失敗，改用 {v}")
                    return path
                except edge_tts.exceptions.NoAudioReceived:
                    await asyncio.sleep(min(attempt, 3))
        raise RuntimeError(f"第 {i} 段語音合成失敗：{text[:30]}…")

    return await asyncio.gather(*(one(i, v, t) for i, (v, t) in enumerate(segments)))


def build_script(items: list[dict], zh_texts: list[str]) -> list[tuple[str, str]]:
    date_en = datetime.now().strftime("%A, %d %B %Y")
    now = datetime.now()
    date_zh = f"{now.year}年{now.month}月{now.day}日"

    segments = [
        (FEMALE_VOICE, f"Good morning, this is your BBC daily briefing for {date_en}. Here are today's top {len(items)} stories."),
        (MALE_VOICE, f"大家早安，歡迎收聽 BBC 每日新聞雙語播報，今天是{date_zh}。以下是今天的{len(items)}則頭條新聞。"),
    ]
    for n, (item, zh) in enumerate(zip(items, zh_texts), 1):
        segments.append((FEMALE_VOICE, f"Story {n}. {item['text']}"))
        segments.append((MALE_VOICE, f"第{n}則。{zh}"))
    segments += [
        (FEMALE_VOICE, "That's all for today's briefing. Thanks for listening."),
        (MALE_VOICE, "以上是今天的新聞播報，感謝您的收聽，我們明天見。"),
    ]
    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description="BBC 每日新聞雙語 podcast")
    parser.add_argument("-n", "--limit", type=int, default=8, help="頭條則數（預設 8）")
    parser.add_argument("--full", action="store_true", help="另外抓文章前兩段內文，讓每段更完整")
    parser.add_argument("--rate", default="+0%", help="語速，例如 +10%% 或 -5%%")
    parser.add_argument("--pause", type=int, default=600, help="段落間停頓毫秒數（預設 600）")
    parser.add_argument("--retries", type=int, default=12, help="男聲失敗重試次數，之後改用備用聲音（預設 12）")
    parser.add_argument("-o", "--output", type=Path, help="輸出 mp3 路徑（預設 output/bbc_YYYYMMDD.mp3）")
    args = parser.parse_args()

    output = args.output or Path("output") / f"bbc_{datetime.now():%Y%m%d}.mp3"
    output.parent.mkdir(parents=True, exist_ok=True)

    print("抓取 BBC 頭條…")
    items = fetch_headlines(args.limit, args.full)
    for n, item in enumerate(items, 1):
        print(f"  {n}. {item['title']}")

    print("翻譯成台灣繁體中文…")
    zh_texts = [to_taiwan_terms(t) for t in translate([item["text"] for item in items])]

    segments = build_script(items, zh_texts)
    output.with_suffix(".txt").write_text(
        "\n\n".join(f"[{'F' if v == FEMALE_VOICE else 'M'}] {t}" for v, t in segments), encoding="utf-8"
    )

    print(f"合成 {len(segments)} 段語音…")
    with tempfile.TemporaryDirectory() as tmp:
        paths = asyncio.run(synthesize(segments, Path(tmp), args.rate, args.retries))
        gap = AudioSegment.silent(duration=args.pause)
        podcast = AudioSegment.empty()
        for p in paths:
            podcast += AudioSegment.from_mp3(p) + gap
        podcast.export(output, format="mp3", bitrate="128k", tags={"title": f"BBC 每日雙語播報 {datetime.now():%Y-%m-%d}"})

    print(f"完成：{output}（{len(podcast) / 60000:.1f} 分鐘），講稿：{output.with_suffix('.txt')}")


if __name__ == "__main__":
    main()
