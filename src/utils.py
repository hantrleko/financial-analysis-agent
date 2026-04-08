"""
公共工具函数。
消除 collector.py / analyzer.py 中重复的 API Key 与代理获取逻辑。
"""

import os
import logging
import time

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_api_key(env_key: str) -> str:
    """从环境变量或 Streamlit secrets 中获取 API Key。"""
    val = os.getenv(env_key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(env_key, "")
    except Exception:
        return ""


def get_proxy() -> dict | None:
    """获取 Gemini API 代理地址。"""
    proxy = os.getenv("GEMINI_PROXY", "")
    if not proxy:
        try:
            import streamlit as st
            proxy = st.secrets.get("GEMINI_PROXY", "")
        except Exception:
            pass
    if proxy:
        logger.info("Using Gemini proxy: %s", proxy)
        return {"https": proxy, "http": proxy}
    logger.warning("GEMINI_PROXY not set — Gemini API calls will go direct (may fail in China)")
    return None


def retry_api_call(func, max_retries: int | None = None, base_delay: float | None = None,
                   retryable_status_codes: tuple = (429, 500, 502, 503, 504)):
    """
    带指数退避的 API 调用重试装饰器。
    区分可重试错误（429、5xx、timeout）和不可重试错误（401、403 等）。
    默认从 src.config 读取 API_MAX_RETRIES / API_RETRY_BASE_DELAY。

    用法：
        result = retry_api_call(lambda: requests.post(url, json=payload, timeout=60))
    """
    from src.config import API_MAX_RETRIES, API_RETRY_BASE_DELAY
    if max_retries is None:
        max_retries = API_MAX_RETRIES
    if base_delay is None:
        base_delay = API_RETRY_BASE_DELAY
    import requests as http_requests

    last_exception = None
    for attempt in range(max_retries):
        try:
            resp = func()
            if hasattr(resp, 'status_code'):
                if resp.status_code < 400:
                    return resp
                if resp.status_code in retryable_status_codes:
                    logger.warning(
                        "Retryable HTTP %d on attempt %d/%d",
                        resp.status_code, attempt + 1, max_retries,
                    )
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                # Non-retryable status or last attempt — return as-is
                return resp
            return resp
        except (http_requests.exceptions.Timeout,
                http_requests.exceptions.ConnectionError) as e:
            last_exception = e
            logger.warning(
                "Network error on attempt %d/%d: %s",
                attempt + 1, max_retries, e,
            )
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
        except Exception as e:
            # Non-retryable exception — raise immediately
            raise

    if last_exception:
        raise last_exception
