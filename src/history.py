import os
import json
import shutil
from datetime import datetime


class HistoryManager:
    def __init__(self, history_dir="history"):
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)

    def save_run(self, news_items, report, query="", sources=None, time_range="",
                 briefing_length="", audio_file=None, pdf_file=None):
        """
        保存一次运行的所有结果到带时间戳的目录。
        返回 run_id（时间戳字符串）。
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.history_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # Save metadata
        metadata = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "sources": sources or [],
            "time_range": time_range,
            "briefing_length": briefing_length,
            "num_articles": len(news_items) if news_items else 0,
            "has_audio": audio_file is not None and os.path.exists(audio_file) if audio_file else False,
            "has_pdf": pdf_file is not None and os.path.exists(pdf_file) if pdf_file else False,
        }
        with open(os.path.join(run_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save news
        if news_items:
            with open(os.path.join(run_dir, "news.json"), "w", encoding="utf-8") as f:
                json.dump(news_items, f, indent=2, ensure_ascii=False)

        # Save report
        if report:
            with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
                f.write(report)

        # Copy audio file
        if audio_file and os.path.exists(audio_file):
            shutil.copy2(audio_file, os.path.join(run_dir, "briefing.mp3"))

        # Copy PDF file
        if pdf_file and os.path.exists(pdf_file):
            shutil.copy2(pdf_file, os.path.join(run_dir, "briefing.pdf"))

        print(f"Run saved to {run_dir}")
        return run_id

    def list_runs(self):
        """
        列出所有历史运行记录，按时间倒序。
        返回 metadata 列表。
        """
        runs = []
        if not os.path.exists(self.history_dir):
            return runs

        for entry in sorted(os.listdir(self.history_dir), reverse=True):
            meta_path = os.path.join(self.history_dir, entry, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    runs.append(json.load(f))
        return runs

    def load_run(self, run_id):
        """
        加载指定运行的完整数据。
        """
        run_dir = os.path.join(self.history_dir, run_id)
        if not os.path.exists(run_dir):
            return None

        result = {"run_id": run_id}

        # Load metadata
        meta_path = os.path.join(run_dir, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                result["metadata"] = json.load(f)

        # Load news
        news_path = os.path.join(run_dir, "news.json")
        if os.path.exists(news_path):
            with open(news_path, "r", encoding="utf-8") as f:
                result["news"] = json.load(f)

        # Load report
        report_path = os.path.join(run_dir, "report.md")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                result["report"] = f.read()

        # Audio path
        audio_path = os.path.join(run_dir, "briefing.mp3")
        if os.path.exists(audio_path):
            result["audio_path"] = audio_path

        # PDF path
        pdf_path = os.path.join(run_dir, "briefing.pdf")
        if os.path.exists(pdf_path):
            result["pdf_path"] = pdf_path

        return result

    def delete_run(self, run_id):
        """删除指定运行记录。"""
        run_dir = os.path.join(self.history_dir, run_id)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
            print(f"Deleted run: {run_id}")
            return True
        return False
