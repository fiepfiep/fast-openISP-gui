import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def mikros_path() -> Path:
    return ROOT / "raw" / "mikros110.tiff"


@pytest.fixture
def test_raw_path() -> Path:
    return ROOT / "raw" / "test.RAW"
