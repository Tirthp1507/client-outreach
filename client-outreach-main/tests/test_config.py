import os

import pytest


def test_config_loads_from_yaml(clean_env):
    from config import get_config

    cfg = get_config()
    assert cfg["pipeline"]["script_provider"] == "template"
    assert cfg["video"]["width"] == 1080
    assert cfg["video"]["height"] == 1920


def test_env_overrides_yaml(clean_env, monkeypatch):
    from config import reload_config

    monkeypatch.setenv("PIPELINE_SCRIPT_PROVIDER", "openai")
    monkeypatch.setenv("VIDEO_WIDTH", "720")
    cfg = reload_config()
    assert cfg["pipeline"]["script_provider"] == "openai"
    assert cfg["video"]["width"] == 720


def test_missing_config_file_produces_empty_config(clean_env, tmp_path):
    from config import get_config, reload_config

    reload_config()  # drop any cached state from other tests
    fake = tmp_path / "empty.yaml"
    fake.write_text("", encoding="utf-8")
    cfg = get_config(fake)
    assert cfg == {}