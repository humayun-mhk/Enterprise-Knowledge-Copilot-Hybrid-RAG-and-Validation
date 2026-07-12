from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402


@pytest.fixture
def tmp_path() -> Path:
    """Workspace-local replacement for pytest's ACL-special Windows temp dirs."""

    path = BACKEND / ".test_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        vector_backend="memory",
        embedding_provider="hash",
        embedding_dimension=128,
        llm_provider="extractive",
        reranker_enabled=False,
        chunk_size=300,
        chunk_overlap=40,
        min_retrieval_score=0.05,
    )
