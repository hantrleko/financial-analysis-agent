"""src/utils.py 单元测试。"""

import os
from unittest.mock import MagicMock
from src.utils import get_api_key, get_proxy, retry_api_call


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "abc123")
    assert get_api_key("TEST_KEY") == "abc123"


def test_get_api_key_missing(monkeypatch):
    monkeypatch.delenv("TEST_KEY", raising=False)
    assert get_api_key("TEST_KEY") == ""


def test_get_proxy_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("GEMINI_PROXY", raising=False)
    result = get_proxy()
    assert result is None


def test_get_proxy_returns_dict_when_set(monkeypatch):
    monkeypatch.setenv("GEMINI_PROXY", "http://proxy:8080")
    result = get_proxy()
    assert result == {"https": "http://proxy:8080", "http": "http://proxy:8080"}


def test_retry_api_call_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    result = retry_api_call(lambda: mock_resp)
    assert result.status_code == 200


def test_retry_api_call_retries_on_429():
    call_count = 0

    def flaky_call():
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 429 if call_count < 3 else 200
        return resp

    result = retry_api_call(flaky_call, max_retries=3, base_delay=0.01)
    assert result.status_code == 200
    assert call_count == 3


def test_retry_api_call_no_retry_on_401():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    result = retry_api_call(lambda: mock_resp, max_retries=3)
    assert result.status_code == 401
