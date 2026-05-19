"""Test cho config.py (Settings) và schemas.py (6 Pydantic output model).

Phủ 4 behavior:
- Test 1: Settings nhận base URL http hợp lệ — giữ nguyên.
- Test 2: Settings nhận base URL scheme ftp — raise ValidationError (chống SSRF).
- Test 3: Settings strip trailing slash khỏi base URL.
- Test 4: 6 Pydantic output model khởi tạo OK với dữ liệu rỗng hợp lệ.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_app.config import Settings
from mcp_app.schemas import AskAnswer, HubList, SearchResult


def test_settings_accepts_valid_http_url() -> None:
    """Test 1: base URL http hợp lệ được giữ nguyên."""
    settings = Settings(api_base_url="http://localhost:8180")
    assert settings.api_base_url == "http://localhost:8180"


def test_settings_rejects_non_http_scheme() -> None:
    """Test 2: scheme ftp bị reject — chống SSRF/misconfiguration."""
    with pytest.raises(ValidationError):
        Settings(api_base_url="ftp://evil")


def test_settings_strips_trailing_slash() -> None:
    """Test 3: trailing slash bị strip khỏi base URL."""
    settings = Settings(api_base_url="http://localhost:8180/")
    assert settings.api_base_url == "http://localhost:8180"


def test_output_models_construct_with_empty_data() -> None:
    """Test 4: 6 output model khởi tạo OK với dữ liệu rỗng hợp lệ."""
    answer = AskAnswer(answer="x [1]", citations=[])
    assert answer.answer == "x [1]"
    assert answer.citations == []

    result = SearchResult(results=[], total=0)
    assert result.total == 0

    hubs = HubList(hubs=[])
    assert hubs.hubs == []
