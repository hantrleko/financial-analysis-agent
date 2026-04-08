from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from datetime import datetime

from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from fpdf import FPDF

from src.config import EDGE_TTS_MAX_CHARS_PER_CHUNK, TTS_MAX_CHARS_PER_CHUNK, VERSION

load_dotenv()

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# 语音预设：按语言分组，每个条目为 {显示名: voice_id}
VOICE_PRESETS = {
    "en": {
        "Rachel (Female)": "21m00Tcm4TlvDq8ikWAM",
        "Adam (Male)": "pNInz6obpgDQGcFmaJgB",
    },
    "zh": {
        "Lily (Female)": "pFZP5JQG7iQjIQuC4Bku",
        "Charlotte (Female)": "XB0fDUnXU5powFXDhCwa",
    },
}

# Edge TTS 语音预设：免费，中文效果极佳
EDGE_VOICE_PRESETS = {
    "en": {
        "Jenny (Female)": "en-US-JennyNeural",
        "Guy (Male)": "en-US-GuyNeural",
    },
    "zh": {
        "晓晓 Xiaoxiao (Female)": "zh-CN-XiaoxiaoNeural",
        "云希 Yunxi (Male)": "zh-CN-YunxiNeural",
        "晓悦 Xiaoyue (Female)": "zh-CN-XiaoyueNeural",
    },
}

# TTS 引擎选项
TTS_ENGINES = {
    "ElevenLabs": "elevenlabs",
    "Edge TTS (Free, 推荐中文)": "edge_tts",
}

# 语言对应的 ElevenLabs 模型
LANGUAGE_MODELS = {
    "en": "eleven_monolingual_v1",
    "zh": "eleven_multilingual_v2",
}

# Emoji / symbol regex: covers supplementary planes, dingbats, misc symbols,
# en-dash, em-dash, smart quotes, and other chars outside Latin-1.
_EMOJI_RE = re.compile(
    r'[\U00010000-\U0010ffff]'   # Supplementary planes (emoji etc.)
    r'|[\u2600-\u27BF]'          # Misc symbols, dingbats
    r'|[\uFE00-\uFE0F]'          # Variation selectors
    r'|[\u2700-\u27BF]'          # Dingbats
    r'|[\u2300-\u23FF]'          # Misc technical
    r'|[\u200D]'                 # Zero-width joiner
    r'|[\u20E3]'                 # Combining enclosing keycap
    r'|[\u2640-\u2642]'          # Gender symbols
    r'|[\u2194-\u21AA]'          # Arrows
    r'|[\u2010-\u2015]'          # Dashes (incl. en-dash, em-dash)
    r'|[\u2018-\u201F]'          # Smart quotes
    r'|[\u2026]'                 # Ellipsis
    r'|[\u2022]'                 # Bullet
)


def _find_cjk_font():
    """Locate a CJK font on the current platform. Returns path or None."""
    system = platform.system()
    if system == "Windows":
        candidates = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf"]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class MediaGenerator:
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        """懒加载 ElevenLabs 客户端：仅在实际调用 ElevenLabs TTS 时才初始化。"""
        if self._client is None:
            if not ELEVENLABS_API_KEY:
                raise ValueError("ELEVENLABS_API_KEY not found in .env — cannot use ElevenLabs engine.")
            self._client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        return self._client

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def generate_audio(self, text: str, output_file: str = "data/daily_briefing.mp3",
                       language: str = "en", voice_name: str | None = None,
                       tts_engine: str = "elevenlabs") -> str | None:
        """
        生成音频。支持 ElevenLabs 和 Edge TTS 两种引擎。
        tts_engine: "elevenlabs" 或 "edge_tts"。
        language: "en" 或 "zh"，决定使用的模型和默认语音。
        voice_name: 语音名称，需匹配对应引擎的预设 key。
        """
        if tts_engine == "edge_tts":
            return self.generate_audio_edge(text, output_file, language, voice_name)

        if not ELEVENLABS_API_KEY:
            logger.warning("Skipping ElevenLabs audio (No API Key). Consider using Edge TTS.")
            return None

        text = self._clean_for_tts(text)
        chunks = self._split_text_for_tts(text, TTS_MAX_CHARS_PER_CHUNK)

        # 选择语音
        presets = VOICE_PRESETS.get(language, VOICE_PRESETS["en"])
        if voice_name and voice_name in presets:
            voice_id = presets[voice_name]
        else:
            voice_id = list(presets.values())[0]

        model_id = LANGUAGE_MODELS.get(language, "eleven_monolingual_v1")

        logger.info("Generating audio (lang=%s, voice=%s, model=%s, chunks=%d)...",
                     language, voice_name, model_id, len(chunks))

        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            if len(chunks) == 1:
                audio = self.client.text_to_speech.convert(
                    voice_id=voice_id,
                    model_id=model_id,
                    optimize_streaming_latency="0",
                    output_format="mp3_22050_32",
                    text=chunks[0],
                    voice_settings=VoiceSettings(
                        stability=0.7,
                        similarity_boost=0.75,
                        style=0.0,
                        use_speaker_boost=True,
                    ),
                )
                with open(output_file, "wb") as f:
                    for chunk in audio:
                        if chunk:
                            f.write(chunk)
            else:
                part_files = []
                for i, text_chunk in enumerate(chunks):
                    part_file = output_file + f".part{i}.mp3"
                    part_files.append(part_file)
                    audio = self.client.text_to_speech.convert(
                        voice_id=voice_id,
                        model_id=model_id,
                        optimize_streaming_latency="0",
                        output_format="mp3_22050_32",
                        text=text_chunk,
                        voice_settings=VoiceSettings(
                            stability=0.7,
                            similarity_boost=0.75,
                            style=0.0,
                            use_speaker_boost=True,
                        ),
                    )
                    with open(part_file, "wb") as f:
                        for chunk in audio:
                            if chunk:
                                f.write(chunk)
                # 合并临时文件（MP3 可直接二进制拼接）
                with open(output_file, "wb") as out:
                    for part_file in part_files:
                        with open(part_file, "rb") as pf:
                            out.write(pf.read())
                for part_file in part_files:
                    os.remove(part_file)

            logger.info("Audio saved to %s", output_file)
            return output_file

        except Exception as e:
            logger.error("Error generating audio: %s", e)
            return None

    def generate_audio_edge(self, text: str, output_file: str = "data/daily_briefing.mp3",
                            language: str = "en", voice_name: str | None = None) -> str | None:
        """
        使用 Edge TTS 生成音频（免费，中文效果极佳）。
        language: "en" 或 "zh"，决定默认语音。
        voice_name: 语音名称，需匹配 EDGE_VOICE_PRESETS 中的 key。
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return None

        text = self._clean_for_tts(text)
        chunks = self._split_text_for_tts(text, EDGE_TTS_MAX_CHARS_PER_CHUNK)

        presets = EDGE_VOICE_PRESETS.get(language, EDGE_VOICE_PRESETS["en"])
        if voice_name and voice_name in presets:
            voice = presets[voice_name]
        else:
            voice = list(presets.values())[0]

        logger.info("Generating audio with Edge TTS (lang=%s, voice=%s, chunks=%d)...",
                     language, voice, len(chunks))

        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # 兼容 Streamlit 等已有事件循环的环境
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()

            def _run_async(coro):
                if loop and loop.is_running():
                    loop.run_until_complete(coro)
                else:
                    asyncio.run(coro)

            if len(chunks) == 1:
                communicate = edge_tts.Communicate(chunks[0], voice)
                _run_async(communicate.save(output_file))
            else:
                part_files = []
                for i, text_chunk in enumerate(chunks):
                    part_file = output_file + f".part{i}.mp3"
                    part_files.append(part_file)
                    communicate = edge_tts.Communicate(text_chunk, voice)
                    _run_async(communicate.save(part_file))
                # 合并临时文件（MP3 可直接二进制拼接）
                with open(output_file, "wb") as out:
                    for part_file in part_files:
                        with open(part_file, "rb") as pf:
                            out.write(pf.read())
                for part_file in part_files:
                    os.remove(part_file)

            logger.info("Audio saved to %s", output_file)
            return output_file
        except Exception as e:
            logger.error("Error generating audio with Edge TTS: %s", e)
            return None

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def generate_pdf(self, report_text: str, output_file: str = "data/daily_briefing.pdf",
                     language: str = "en", title: str = "Financial Analysis Briefing") -> str | None:
        """
        将分析报告导出为 PDF，支持中英文。
        增强：封面页 + 目录 + 页眉页脚 + 页码。
        """
        logger.info("Generating PDF (lang=%s)...", language)

        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=20)

            # 注册中文字体（跨平台检测）
            if language == "zh":
                font_path = _find_cjk_font()
                if font_path:
                    pdf.add_font("cjk", "", font_path)
                    pdf.add_font("cjk", "B", font_path)
                    font_name = "cjk"
                else:
                    logger.warning("CJK font not found on this system, falling back to Helvetica.")
                    font_name = "Helvetica"
            else:
                font_name = "Helvetica"

            # ===== Cover page =====
            pdf.add_page()
            pdf.ln(50)
            pdf.set_font(font_name, "B", 28)
            pdf.cell(0, 14, self._strip_emoji(title), new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(8)
            pdf.set_font(font_name, "", 14)
            pdf.cell(0, 10, datetime.now().strftime("%Y-%m-%d %H:%M"),
                     new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(4)
            pdf.set_font(font_name, "", 11)
            pdf.cell(0, 8, f"Version {VERSION}",
                     new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(30)
            # Horizontal rule
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.line(x + 40, y, x + 150, y)
            pdf.ln(8)
            disclaimer = (
                "AI 自动生成，仅供参考。不构成投资建议。"
                if language == "zh"
                else "Auto-generated by AI. Not financial advice."
            )
            pdf.set_font(font_name, "", 9)
            pdf.cell(0, 6, disclaimer, new_x="LMARGIN", new_y="NEXT", align="C")

            # ===== TOC page =====
            toc_entries = self._extract_toc(report_text)
            if toc_entries:
                pdf.add_page()
                toc_title = "目录" if language == "zh" else "Table of Contents"
                pdf.set_font(font_name, "B", 18)
                pdf.cell(0, 12, toc_title, new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(8)
                pdf.set_font(font_name, "", 11)
                for level, heading in toc_entries:
                    indent = (level - 1) * 8
                    pdf.cell(indent)
                    prefix = "• " if level > 1 else ""
                    pdf.cell(0, 7, f"{prefix}{self._strip_emoji(heading)}",
                             new_x="LMARGIN", new_y="NEXT")

            # ===== Content pages =====
            pdf.add_page()
            self._render_markdown(pdf, report_text, font_name)

            # ===== Page numbers (header + footer) =====
            total_pages = pdf.pages_count
            for page_num in range(1, total_pages + 1):
                pdf.page = page_num
                # Footer: page number
                pdf.set_y(-15)
                pdf.set_font(font_name, "", 8)
                pdf.cell(0, 8, f"- {page_num} / {total_pages} -", align="C")

            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            pdf.output(output_file)
            logger.info("PDF saved to %s", output_file)
            return output_file

        except Exception as e:
            logger.error("Error generating PDF: %s", e)
            return None

    @staticmethod
    def _extract_toc(text: str) -> list[tuple[int, str]]:
        """Extract headings from markdown text for TOC generation."""
        entries: list[tuple[int, str]] = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                entries.append((1, line[2:]))
            elif line.startswith("## "):
                entries.append((2, line[3:]))
            elif line.startswith("### "):
                entries.append((3, line[4:]))
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_markdown(self, pdf: FPDF, text: str, font_name: str) -> None:
        """增强型 Markdown 渲染：支持标题、列表、编号列表、表格、分隔线"""
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()

            if not stripped:
                pdf.ln(4)
                i += 1
                continue

            # 表格：检测 | 开头的连续行
            if stripped.startswith("|") and "|" in stripped[1:]:
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                self._render_table(pdf, table_lines, font_name)
                pdf.ln(4)
                continue

            # 标题
            if stripped.startswith("#### "):
                pdf.set_font(font_name, "B", 12)
                pdf.multi_cell(0, 7, self._strip_md(stripped[5:]))
                pdf.ln(2)
            elif stripped.startswith("### "):
                pdf.set_font(font_name, "B", 13)
                pdf.multi_cell(0, 7, self._strip_md(stripped[4:]))
                pdf.ln(2)
            elif stripped.startswith("## "):
                pdf.set_font(font_name, "B", 15)
                pdf.multi_cell(0, 8, self._strip_md(stripped[3:]))
                pdf.ln(3)
            elif stripped.startswith("# "):
                pdf.set_font(font_name, "B", 17)
                pdf.multi_cell(0, 9, self._strip_md(stripped[2:]))
                pdf.ln(4)
            # 无序列表
            elif stripped.startswith(("- ", "* ")):
                pdf.set_font(font_name, "", 11)
                pdf.cell(6)
                pdf.multi_cell(0, 6, "- " + self._strip_md(stripped[2:]))
                pdf.ln(1)
            # 编号列表 (1. 2. 3. ...)
            elif re.match(r'^(\d+)\.\s', stripped):
                m = re.match(r'^(\d+)\.\s(.*)', stripped)
                pdf.set_font(font_name, "", 11)
                pdf.cell(6)
                pdf.multi_cell(0, 6, f"{m.group(1)}. " + self._strip_md(m.group(2)))
                pdf.ln(1)
            # 分隔线
            elif stripped.startswith("---") or stripped.startswith("***"):
                pdf.ln(3)
                x = pdf.get_x()
                y = pdf.get_y()
                pdf.line(x, y, x + 180, y)
                pdf.ln(3)
            # 引用块
            elif stripped.startswith("> "):
                pdf.set_font(font_name, "", 11)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(8)
                pdf.multi_cell(0, 6, self._strip_md(stripped[2:]))
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)
            else:
                pdf.set_font(font_name, "", 11)
                pdf.multi_cell(0, 6, self._strip_md(stripped))
                pdf.ln(1)

            i += 1

    def _render_table(self, pdf: FPDF, table_lines: list[str], font_name: str) -> None:
        """渲染 Markdown 表格到 PDF"""
        if len(table_lines) < 2:
            return

        # 解析行
        rows = []
        for line in table_lines:
            cells = [c.strip() for c in line.strip("|").split("|")]
            # 跳过分隔行 (--- | ---)
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            rows.append(cells)

        if not rows:
            return

        num_cols = max(len(r) for r in rows)
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        col_width = page_width / num_cols

        for row_idx, row in enumerate(rows):
            # 补齐列数
            while len(row) < num_cols:
                row.append("")

            if row_idx == 0:
                pdf.set_font(font_name, "B", 10)
            else:
                pdf.set_font(font_name, "", 10)

            for cell in row:
                pdf.cell(col_width, 7, self._strip_md(cell), border=1, align="C")
            pdf.ln()

    @staticmethod
    def _strip_emoji(text: str) -> str:
        """Remove emoji and special symbols that common PDF fonts cannot render."""
        return _EMOJI_RE.sub('', text)

    @staticmethod
    def _strip_md(text: str) -> str:
        """去除 Markdown 格式符号 and emoji/symbols unsafe for PDF fonts."""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # [link](url) → link
        text = _EMOJI_RE.sub('', text)
        return text

    @staticmethod
    def _split_text_for_tts(text: str, max_chars: int) -> list[str]:
        """将长文本按段落边界分割为不超过 max_chars 的块。"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current = ""
        for paragraph in text.split("\n\n"):
            if len(current) + len(paragraph) + 2 > max_chars:
                if current:
                    chunks.append(current.strip())
                current = paragraph
            else:
                current = current + "\n\n" + paragraph if current else paragraph
        if current.strip():
            chunks.append(current.strip())
        return chunks if chunks else [text[:max_chars]]

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """Strip Markdown formatting and emoji so TTS engines receive clean prose."""
        # Remove header markers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Remove bold / italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        # Remove inline code
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Remove table rows (lines that start/end with |)
        text = re.sub(r'^\|.*\|$', '', text, flags=re.MULTILINE)
        # Remove horizontal rules
        text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\*{3,}$', '', text, flags=re.MULTILINE)
        # Remove blockquote markers
        text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
        # Convert links to just text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Remove emoji
        text = _EMOJI_RE.sub('', text)
        # Collapse multiple blank lines into one
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = MediaGenerator()
    text = "This is a test of the automated financial analysis system. Markets are up today."
    audio = gen.generate_audio(text, "data/test_audio.mp3", language="en",
                               voice_name="Rachel (Female)")
    gen.generate_pdf("# Test Report\n\nMarkets are **up** today.\n\n- Point 1\n- Point 2",
                     "data/test_report.pdf", language="en")
