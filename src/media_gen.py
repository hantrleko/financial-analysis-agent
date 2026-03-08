import os
import re
import asyncio
from datetime import datetime
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

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


class MediaGenerator:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        """懒加载 ElevenLabs 客户端：仅在实际调用 ElevenLabs TTS 时才初始化。"""
        if self._client is None:
            if not ELEVENLABS_API_KEY:
                raise ValueError("ELEVENLABS_API_KEY not found in .env — cannot use ElevenLabs engine.")
            self._client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        return self._client

    def generate_audio(self, text, output_file="data/daily_briefing.mp3",
                       language="en", voice_name=None, tts_engine="elevenlabs"):
        """
        生成音频。支持 ElevenLabs 和 Edge TTS 两种引擎。
        tts_engine: "elevenlabs" 或 "edge_tts"。
        language: "en" 或 "zh"，决定使用的模型和默认语音。
        voice_name: 语音名称，需匹配对应引擎的预设 key。
        """
        if tts_engine == "edge_tts":
            return self.generate_audio_edge(text, output_file, language, voice_name)

        if not ELEVENLABS_API_KEY:
            print("Skipping ElevenLabs audio (No API Key). Consider using Edge TTS.")
            return None

        # 选择语音
        presets = VOICE_PRESETS.get(language, VOICE_PRESETS["en"])
        if voice_name and voice_name in presets:
            voice_id = presets[voice_name]
        else:
            voice_id = list(presets.values())[0]

        model_id = LANGUAGE_MODELS.get(language, "eleven_monolingual_v1")

        print(f"Generating audio (lang={language}, voice={voice_name}, model={model_id})...")

        try:
            audio = self.client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model_id,
                optimize_streaming_latency="0",
                output_format="mp3_22050_32",
                text=text,
                voice_settings=VoiceSettings(
                    stability=0.7,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )

            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "wb") as f:
                for chunk in audio:
                    if chunk:
                        f.write(chunk)

            print(f"Audio saved to {output_file}")
            return output_file

        except Exception as e:
            print(f"Error generating audio: {e}")
            return None

    def generate_audio_edge(self, text, output_file="data/daily_briefing.mp3",
                            language="en", voice_name=None):
        """
        使用 Edge TTS 生成音频（免费，中文效果极佳）。
        language: "en" 或 "zh"，决定默认语音。
        voice_name: 语音名称，需匹配 EDGE_VOICE_PRESETS 中的 key。
        """
        try:
            import edge_tts
        except ImportError:
            print("Error: edge-tts not installed. Run: pip install edge-tts")
            return None

        presets = EDGE_VOICE_PRESETS.get(language, EDGE_VOICE_PRESETS["en"])
        if voice_name and voice_name in presets:
            voice = presets[voice_name]
        else:
            voice = list(presets.values())[0]

        print(f"Generating audio with Edge TTS (lang={language}, voice={voice})...")

        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            communicate = edge_tts.Communicate(text, voice)

            # 兼容 Streamlit 等已有事件循环的环境
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()

            asyncio.run(communicate.save(output_file))
            print(f"Audio saved to {output_file}")
            return output_file
        except Exception as e:
            print(f"Error generating audio with Edge TTS: {e}")
            return None

    def generate_pdf(self, report_text, output_file="data/daily_briefing.pdf",
                     language="en", title="Financial Analysis Briefing"):
        """
        将分析报告导出为 PDF，支持中英文。
        """
        print(f"Generating PDF (lang={language})...")

        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # 注册中文字体（Windows 系统自带微软雅黑）
            if language == "zh":
                font_path = r"C:\Windows\Fonts\msyh.ttc"
                if os.path.exists(font_path):
                    pdf.add_font("msyh", "", font_path)
                    pdf.add_font("msyh", "B", font_path)
                    font_name = "msyh"
                else:
                    print("Warning: Microsoft YaHei font not found, falling back to Helvetica.")
                    font_name = "Helvetica"
            else:
                font_name = "Helvetica"

            # 标题
            pdf.set_font(font_name, "B", 18)
            pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(4)

            # 日期
            pdf.set_font(font_name, "", 10)
            pdf.cell(0, 8, datetime.now().strftime("%Y-%m-%d %H:%M"),
                     new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(8)

            # 渲染 Markdown 内容
            self._render_markdown(pdf, report_text, font_name)

            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            pdf.output(output_file)
            print(f"PDF saved to {output_file}")
            return output_file

        except Exception as e:
            print(f"Error generating PDF: {e}")
            return None

    def _render_markdown(self, pdf, text, font_name):
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
                pdf.multi_cell(0, 6, "• " + self._strip_md(stripped[2:]))
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

    def _render_table(self, pdf, table_lines, font_name):
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
    def _strip_md(text):
        """去除 Markdown 格式符号"""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # [link](url) → link
        return text


if __name__ == "__main__":
    gen = MediaGenerator()
    text = "This is a test of the automated financial analysis system. Markets are up today."
    audio = gen.generate_audio(text, "data/test_audio.mp3", language="en",
                               voice_name="Rachel (Female)")
    gen.generate_pdf("# Test Report\n\nMarkets are **up** today.\n\n- Point 1\n- Point 2",
                     "data/test_report.pdf", language="en")
