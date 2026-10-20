#!/usr/bin/env python3
"""
BBC 每日雙語新聞 Podcast 產生器
- 抓取 BBC News 今日新聞頭條 (RSS)
- 英國女聲播報英文原文段落
- 台灣男聲接續以繁體中文解說
- 自動合成高品質 MP3 Podcast 檔案
"""

import argparse
import asyncio
import datetime
import html
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# 確保 Windows 控制台支援 UTF-8 與 Emoji 輸出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import feedparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator
import edge_tts
from pydub import AudioSegment


# 預設語音角色設定
# 女聲：en-GB-SoniaNeural (BBC 經典英式英文，清晰沉穩)
# 男聲：zh-TW-YunJheNeural (台灣繁體中文 雲哲，親切自然)
DEFAULT_FEMALE_VOICE = "en-GB-SoniaNeural"
DEFAULT_MALE_VOICE = "zh-TW-YunJheNeural"
BBC_FEED_URL = "https://feeds.bbci.co.uk/news/rss.xml"


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str
    published: str


@dataclass
class PodcastSegment:
    speaker: str         # "female" 或 "male"
    voice: str           # edge-tts voice id
    text: str            # 播報文字
    label: str           # 段落標籤 (如 "Opening", "News 1 - EN", "News 1 - TW", "Closing")


def clean_text(raw_html: str) -> str:
    """清理 HTML 標籤與特殊字元，保留純文字"""
    if not raw_html:
        return ""
    # 解碼 HTML 實體
    text = html.unescape(raw_html)
    soup = BeautifulSoup(text, "html.parser")
    clean = soup.get_text(separator=" ", strip=True)
    # 壓縮多餘空白
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class BBCNewsFetcher:
    """負責抓取與解析 BBC News RSS 頭條新聞"""

    def __init__(self, feed_url: str = BBC_FEED_URL):
        self.feed_url = feed_url

    def fetch_top_stories(self, limit: int = 5) -> List[NewsItem]:
        print(f"📡 正在從 BBC News 抓取最新頭條新聞 (來源: {self.feed_url})...")
        feed = feedparser.parse(self.feed_url)

        if not feed.entries:
            print("⚠️ 無法獲取新聞項目，請檢查網路連線或稍後再試。")
            return []

        items: List[NewsItem] = []
        for entry in feed.entries:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
            link = entry.get("link", "")
            published = entry.get("published", "")

            # 過濾過短或無效項目
            if not title or len(title) < 5:
                continue

            # 避免重複標題
            if any(item.title == title for item in items):
                continue

            items.append(NewsItem(
                title=title,
                summary=summary,
                link=link,
                published=published
            ))

            if len(items) >= limit:
                break

        print(f"✅ 成功擷取 {len(items)} 則今日國際頭條新聞！")
        return items


class TranslatorService:
    """具備多層 Fallback 的繁體中文翻譯服務"""

    @staticmethod
    def to_traditional_chinese(text: str) -> str:
        """嘗試透過多個後端翻譯為台灣繁體中文 (zh-TW)"""
        if not text or not text.strip():
            return ""

        # 1. 優先嘗試 GoogleTranslator
        try:
            res = GoogleTranslator(source="auto", target="zh-TW").translate(text)
            if res and res.strip():
                return res.strip()
        except Exception:
            pass

        # 2. 次選嘗試 MyMemoryTranslator
        try:
            time.sleep(0.3)
            res = MyMemoryTranslator(source="en-GB", target="zh-TW").translate(text)
            if res and res.strip():
                return res.strip()
        except Exception as e:
            print(f"⚠️ 翻譯備用方案發生錯誤: {e}")

        # 若都失敗，回傳原文並標註
        return text


class PodcastScriptBuilder:
    """組織男女雙主播交替播報的 Podcast 腳本"""

    def __init__(
        self,
        female_voice: str = DEFAULT_FEMALE_VOICE,
        male_voice: str = DEFAULT_MALE_VOICE
    ):
        self.female_voice = female_voice
        self.male_voice = male_voice
        self.translator = TranslatorService()

    def build_script(self, news_items: List[NewsItem]) -> List[PodcastSegment]:
        segments: List[PodcastSegment] = []
        today_str = datetime.date.today().strftime("%Y年%m月%d日")
        today_en_str = datetime.date.today().strftime("%B %d, %Y")

        print("📝 正在編排雙主播雙語 Podcast 腳本與中文轉譯...")

        # --- 1. 片頭 Opening ---
        female_intro = (
            f"Hello and welcome to BBC World News Today. Today is {today_en_str}. "
            "Here are the top stories shaping our world."
        )
        male_intro = (
            f"各位聽眾朋友大家好，今天是 {today_str}，歡迎收聽 BBC 每日雙語新聞速報。"
            "接下來將由我們為您帶來最新的國際重要頭條與繁體中文重點解析。"
        )

        segments.append(PodcastSegment(
            speaker="female",
            voice=self.female_voice,
            text=female_intro,
            label="Opening - Female"
        ))
        segments.append(PodcastSegment(
            speaker="male",
            voice=self.male_voice,
            text=male_intro,
            label="Opening - Male"
        ))

        # --- 2. 各則新聞輪替 (女聲英文 -> 男聲台灣繁中) ---
        num_chinese = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

        for idx, item in enumerate(news_items):
            count_tw = num_chinese[idx] if idx < len(num_chinese) else str(idx + 1)
            print(f"  🔹 處理第 {idx + 1} 則新聞: {item.title[:45]}...")

            # 女聲英文播報：第幾則標題 + 摘要
            en_speech = f"Story number {idx + 1}. {item.title}. "
            if item.summary:
                en_speech += f"{item.summary}"

            # 翻譯為台灣繁中
            tw_title = self.translator.to_traditional_chinese(item.title)
            tw_summary = ""
            if item.summary:
                tw_summary = self.translator.to_traditional_chinese(item.summary)

            # 男聲中文主持口吻：親切轉場
            zh_transitions = [
                f"第{count_tw}則新聞焦點：{tw_title}。",
                f"接下來關心第{count_tw}則報導：{tw_title}。",
                f"第{count_tw}則頭條關注：{tw_title}。",
                f"另一則重要消息是：{tw_title}。",
            ]
            zh_trans = zh_transitions[idx % len(zh_transitions)]

            zh_speech = f"{zh_trans}"
            if tw_summary:
                zh_speech += f" BBC 報導指出，{tw_summary}"

            # 加入段落
            segments.append(PodcastSegment(
                speaker="female",
                voice=self.female_voice,
                text=en_speech,
                label=f"News {idx + 1} - English (Female)"
            ))
            segments.append(PodcastSegment(
                speaker="male",
                voice=self.male_voice,
                text=zh_speech,
                label=f"News {idx + 1} - Traditional Chinese (Male)"
            ))

        # --- 3. 片尾 Closing ---
        female_outro = (
            "That brings us to the end of today's BBC World News briefing. "
            "Thank you for joining us, and stay tuned for more global updates."
        )
        male_outro = (
            "以上就是今天的國際頭條精選與中文解析。"
            "感謝您的收聽，祝您有美好的一天，我們明天同一時間再會！"
        )

        segments.append(PodcastSegment(
            speaker="female",
            voice=self.female_voice,
            text=female_outro,
            label="Closing - Female"
        ))
        segments.append(PodcastSegment(
            speaker="male",
            voice=self.male_voice,
            text=male_outro,
            label="Closing - Male"
        ))

        print(f"✨ 腳本製作完成，共計 {len(segments)} 個播報音軌片段！")
        return segments


class AudioSynthesizer:
    """利用 edge-tts 合成語音並使用 pydub 拼接為完整 Podcast MP3"""

    @staticmethod
    async def _synthesize_single_segment(
        segment: PodcastSegment,
        output_path: str,
        max_retries: int = 5
    ):
        """合成單一片段並提供指數退避重試與備用語音機制"""
        # 備用語音庫
        fallback_voices = {
            "female": ["en-GB-SoniaNeural", "en-GB-MaisieNeural", "en-US-AvaNeural", "en-US-JennyNeural"],
            "male": ["zh-TW-YunJheNeural", "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural", "zh-CN-YunyangNeural"]
        }
        voices_to_try = [segment.voice]
        for fv in fallback_voices.get(segment.speaker, []):
            if fv not in voices_to_try:
                voices_to_try.append(fv)

        for current_voice in voices_to_try:
            for attempt in range(1, max_retries + 1):
                try:
                    communicate = edge_tts.Communicate(text=segment.text, voice=current_voice)
                    await communicate.save(output_path)
                    return True
                except Exception as e:
                    if attempt < max_retries:
                        sleep_time = 2.0 * attempt
                        print(f"    ⏳ [重試 {attempt}/{max_retries}] 語音合成暫時無回應，等待 {sleep_time:.1f} 秒後重試...")
                        await asyncio.sleep(sleep_time)
                    else:
                        print(f"    ⚠️ 語音 {current_voice} 嘗試多次失敗 ({e})，嘗試切換備用語音...")
                        break
        raise RuntimeError(f"合成語音失敗 ({segment.label}): 所有備用語音皆嘗試完畢")

    @classmethod
    async def synthesize_all(
        cls,
        segments: List[PodcastSegment],
        output_mp3_path: str,
        keep_temp: bool = False
    ) -> str:
        temp_dir = tempfile.mkdtemp(prefix="bbc_podcast_")
        temp_files: List[str] = []

        print(f"🎙️ 開始進行高音質語音合成 (TTS)...")

        try:
            for idx, seg in enumerate(segments):
                seg_filename = os.path.join(temp_dir, f"seg_{idx:03d}_{seg.speaker}.mp3")
                print(f"  [{idx + 1}/{len(segments)}] {seg.label} ({'女聲英音' if seg.speaker == 'female' else '男聲台繁'})...")
                await cls._synthesize_single_segment(seg, seg_filename)
                temp_files.append(seg_filename)
                # 微幅休眠避免微軟伺服器頻繁呼叫
                await asyncio.sleep(0.8)

            print("🎧 正在混音與拼接音訊檔案 (Audio Mixing)...")
            combined_audio = AudioSegment.empty()

            # 設定間隔停頓時間 (毫秒)
            pause_between_speakers = AudioSegment.silent(duration=600)  # 同則男女交替間隔 0.6 秒
            pause_between_news = AudioSegment.silent(duration=1100)      # 新聞條目間隔 1.1 秒
            pause_opening = AudioSegment.silent(duration=800)           # 開頭與結尾間隔 0.8 秒

            for idx, file_path in enumerate(temp_files):
                audio_clip = AudioSegment.from_file(file_path)
                combined_audio += audio_clip

                # 插入適當的呼吸停頓
                if idx < len(temp_files) - 1:
                    current_seg = segments[idx]
                    next_seg = segments[idx + 1]

                    if "Opening" in current_seg.label and "Opening" in next_seg.label:
                        combined_audio += pause_between_speakers
                    elif "Opening" in current_seg.label:
                        combined_audio += pause_opening
                    elif "Closing" in current_seg.label:
                        combined_audio += pause_between_speakers
                    elif current_seg.speaker == "female" and next_seg.speaker == "male":
                        # 女聲英文 -> 男聲中文
                        combined_audio += pause_between_speakers
                    else:
                        # 男聲中文 -> 下一則新聞女聲英文
                        combined_audio += pause_between_news

            # 確保目標輸出目錄存在
            target_path = Path(output_mp3_path).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"💾 正在匯出最終 MP3 檔案至: {target_path}")
            combined_audio.export(
                str(target_path),
                format="mp3",
                bitrate="192k",
                tags={
                    "title": f"BBC News Daily Briefing - {datetime.date.today().isoformat()}",
                    "artist": "BBC Bilingual Podcast (Sonia & YunJhe)",
                    "album": "BBC Daily News Bilingual Podcast",
                    "date": str(datetime.date.today().year),
                }
            )

            # 計算總時長
            duration_sec = len(combined_audio) / 1000.0
            mins = int(duration_sec // 60)
            secs = int(duration_sec % 60)
            print(f"🎉 製作成功！音訊總長度: {mins} 分 {secs} 秒，檔案大小: {os.path.getsize(target_path) / 1024 / 1024:.2f} MB")

            return str(target_path)

        finally:
            if not keep_temp:
                for tf in temp_files:
                    if os.path.exists(tf):
                        try:
                            os.remove(tf)
                        except OSError:
                            pass
                if os.path.exists(temp_dir):
                    try:
                        os.rmdir(temp_dir)
                    except OSError:
                        pass
            else:
                print(f"📁 暫存分段音訊已保留於: {temp_dir}")


def print_script_preview(segments: List[PodcastSegment]):
    """在終端機漂亮地列印出整份 Podcast 播報腳本"""
    print("\n" + "=" * 65)
    print("📻 【BBC 雙語新聞播報 Podcast 腳本預覽】")
    print("=" * 65)
    for seg in segments:
        icon = "👩🏻‍💼 [英音女主播]" if seg.speaker == "female" else "👨🏻‍💼 [台繁男主持]"
        print(f"\n{icon} ({seg.label}):")
        print(f"   {seg.text}")
    print("\n" + "=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="BBC 今日頭條雙語 Podcast 產生器 (女生英音 + 男生台灣繁中輪流播報)"
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=5,
        help="欲抓取與播報的新聞頭條則數 (預設: 5)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="輸出 MP3 檔案路徑 (預設為 output/bbc_podcast_YYYYMMDD_HHMM.mp3)"
    )
    parser.add_argument(
        "--female-voice",
        type=str,
        default=DEFAULT_FEMALE_VOICE,
        help=f"女聲 (英文) 語音模型 (預設: {DEFAULT_FEMALE_VOICE})"
    )
    parser.add_argument(
        "--male-voice",
        type=str,
        default=DEFAULT_MALE_VOICE,
        help=f"男聲 (台灣繁中) 語音模型 (預設: {DEFAULT_MALE_VOICE})"
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="僅生成與預覽播報腳本，不進行 TTS 音訊合成"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留各段合成的暫存 mp3 片段"
    )

    args = parser.parse_args()

    # 決定輸出路徑
    if not args.output:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        args.output = str(output_dir / f"bbc_podcast_{timestamp}.mp3")

    # 1. 抓取 BBC 新聞
    fetcher = BBCNewsFetcher()
    news_items = fetcher.fetch_top_stories(limit=args.count)
    if not news_items:
        print("❌ 未能獲取任何新聞，程式結束。")
        sys.exit(1)

    # 2. 構建雙主播腳本
    builder = PodcastScriptBuilder(
        female_voice=args.female_voice,
        male_voice=args.male_voice
    )
    segments = builder.build_script(news_items)

    # 3. 預覽腳本
    print_script_preview(segments)

    if args.preview_only:
        print("💡 您開啟了 --preview-only，已跳過語音合成。")
        return

    # 4. 語音合成與混音輸出
    asyncio.run(AudioSynthesizer.synthesize_all(
        segments=segments,
        output_mp3_path=args.output,
        keep_temp=args.keep_temp
    ))


if __name__ == "__main__":
    main()
