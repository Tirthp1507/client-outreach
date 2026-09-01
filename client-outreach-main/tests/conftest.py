import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def clean_env(monkeypatch):
    """Unglobalize config so tests don't pollute each other."""
    import config as cfg

    cfg.reload_config()
    yield monkeypatch
    cfg.reload_config()
    for key in list(os.environ):
        if key.startswith("PIPELINE_") or key.startswith("SCRIPT_") \
                or key.startswith("VIDEO_") or key.startswith("VOICE_"):
            os.environ.pop(key, None)