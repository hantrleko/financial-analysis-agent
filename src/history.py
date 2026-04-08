from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime

from src.config import HISTORY_MAX_AGE_DAYS, HISTORY_MAX_RUNS

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, history_dir: str = "history") -> None:
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)

    def _generate_run_id(self) -> str:
        """生成唯一 run_id，优先使用微秒时间戳，并处理极端并发冲突。"""
        base = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_id = base
        suffix = 1
        while os.path.exists(os.path.join(self.history_dir, run_id)):
            run_id = f"{base}_{suffix}"
            suffix += 1
        return run_id

    def save_run(self, news_items: list[dict], report: str, query: str = "",
                 sources: list[str] | None = None, time_range: str = "",
                 briefing_length: str = "", audio_file: str | None = None,
                 pdf_file: str | None = None) -> str:
        """
        保存一次运行的所有结果到带时间戳的目录。
        返回 run_id（时间戳字符串）。
        """
        run_id = self._generate_run_id()
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

        logger.info("Run saved to %s", run_dir)
        self.cleanup()
        return run_id

    def list_runs(self) -> list[dict]:
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

    def load_run(self, run_id: str) -> dict | None:
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

    def delete_run(self, run_id: str) -> bool:
        """删除指定运行记录。"""
        run_dir = os.path.join(self.history_dir, run_id)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
            logger.info("Deleted run: %s", run_id)
            return True
        return False

    def search_runs(self, keyword: str | None = None,
                    date_from: str | datetime | None = None,
                    date_to: str | datetime | None = None) -> list[dict]:
        """
        搜索/过滤历史记录。
        keyword: 在 query 和 report 中搜索关键词（不区分大小写）
        date_from: 起始日期 (str "YYYY-MM-DD" 或 datetime)
        date_to: 结束日期 (str "YYYY-MM-DD" 或 datetime)
        返回符合条件的 metadata 列表（按时间倒序）。
        """
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from)
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to)
        if date_to and not date_to.hour and not date_to.minute and not date_to.second:
            date_to = date_to.replace(hour=23, minute=59, second=59)

        results = []
        for meta in self.list_runs():
            # Filter by date range
            ts = datetime.fromisoformat(meta["timestamp"])
            if date_from and ts < date_from:
                continue
            if date_to and ts > date_to:
                continue

            # Filter by keyword
            if keyword:
                kw_lower = keyword.lower()
                query_text = meta.get("query", "")
                if kw_lower in query_text.lower():
                    results.append(meta)
                    continue
                # Keyword not in query — check report content
                report_path = os.path.join(
                    self.history_dir, meta["run_id"], "report.md"
                )
                if os.path.exists(report_path):
                    with open(report_path, "r", encoding="utf-8") as f:
                        report_text = f.read()
                    if kw_lower in report_text.lower():
                        results.append(meta)
                        continue
            else:
                results.append(meta)

        return results

    def cleanup(self) -> int:
        """自动清理超量和过期的历史记录。"""
        runs = self.list_runs()  # 已按时间倒序

        now = datetime.now()
        deleted = 0

        for i, run in enumerate(runs):
            run_id = run.get("run_id", "")
            should_delete = False

            # 超过最大保留数
            if i >= HISTORY_MAX_RUNS:
                should_delete = True

            # 超过最大保留天数
            try:
                ts = datetime.fromisoformat(run["timestamp"])
                age_days = (now - ts).days
                if age_days > HISTORY_MAX_AGE_DAYS:
                    should_delete = True
            except (KeyError, ValueError):
                pass

            if should_delete:
                self.delete_run(run_id)
                deleted += 1

        if deleted:
            logger.info("Cleaned up %d old history records.", deleted)
        return deleted

    def get_run_count(self) -> int:
        """返回历史记录总数。"""
        return len(self.list_runs())
