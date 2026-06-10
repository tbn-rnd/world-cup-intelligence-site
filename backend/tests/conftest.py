from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).parent / "fixtures"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def knowledge_dir() -> Path:
    return KNOWLEDGE_DIR
