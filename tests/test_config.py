import os
import pytest
from codemate.config import Config


def test_default_config(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    
    cfg = Config()
    assert cfg.model_name == "deepseek-flash"
    assert "deepseek.com" in cfg.base_url
    assert cfg.max_iterations == 10
    assert cfg.temperature == 0.2
    assert cfg.has_valid_api_key() is False


def test_env_override(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-coder")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "15")
    
    cfg = Config.from_env()
    assert cfg.api_key == "test-key-123"
    assert cfg.base_url == "https://custom.deepseek.com/v1"
    assert cfg.model_name == "deepseek-coder"
    assert cfg.max_iterations == 15
    assert cfg.has_valid_api_key() is True
