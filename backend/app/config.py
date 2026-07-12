from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


@dataclass(slots=True)
class Settings:
    """Runtime configuration with safe, offline-first defaults."""

    app_name: str = "Enterprise Knowledge Copilot"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])

    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1] / "data")
    database_url: str = ""
    upload_dir: Path | None = None
    chroma_dir: Path | None = None
    evaluation_dir: Path | None = None
    max_upload_mb: int = 25

    vector_backend: str = "auto"  # auto | chroma | memory
    embedding_provider: str = "hash"  # hash | openai | ollama | gemini
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 384
    llm_provider: str = "extractive"  # extractive | openai | anthropic | gemini | ollama
    llm_model: str = ""
    llm_temperature: float = 0.0
    ollama_base_url: str = "http://localhost:11434"
    input_cost_per_million_tokens: float = 0.0
    output_cost_per_million_tokens: float = 0.0

    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_n: int = 10
    retrieval_candidate_k: int = 20
    default_top_k: int = 5
    rrf_k: int = 60
    dense_weight: float = 0.6
    sparse_weight: float = 0.4
    min_retrieval_score: float = 0.08

    chunk_size: int = 900
    chunk_overlap: int = 150
    validation_support_threshold: float = 0.45
    validation_min_coverage: float = 0.8
    max_answer_sentences: int = 5

    prompt_version: str = "grounded-answer-v1"
    validator_prompt_version: str = "claim-validator-v1"
    retrieval_config_version: str = "hybrid-rrf-v1"
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "enterprise-knowledge-copilot"

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir).resolve()
        self.upload_dir = Path(self.upload_dir or self.data_dir / "uploads").resolve()
        self.chroma_dir = Path(self.chroma_dir or self.data_dir / "chroma").resolve()
        self.evaluation_dir = Path(self.evaluation_dir or self.data_dir / "evaluations").resolve()
        if not self.database_url:
            self.database_url = f"sqlite:///{(self.data_dir / 'copilot.db').as_posix()}"

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("This reference implementation currently requires a sqlite:/// database URL")
        return Path(self.database_url[len(prefix) :]).resolve()

    def ensure_directories(self) -> None:
        assert self.upload_dir is not None
        assert self.chroma_dir is not None
        assert self.evaluation_dir is not None
        for path in (self.data_dir, self.upload_dir, self.chroma_dir, self.evaluation_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
        upload_dir = os.getenv("UPLOAD_DIR")
        chroma_dir = os.getenv("CHROMA_DIR") or os.getenv("CHROMA_PERSIST_DIR")
        origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if item.strip()]
        evaluation_dir = os.getenv("EVALUATION_DIR") or os.getenv("EVALUATION_RESULTS_DIR")
        return cls(
            app_name=os.getenv("APP_NAME", "Enterprise Knowledge Copilot"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            environment=os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "development",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cors_origins=origins,
            data_dir=base,
            database_url=os.getenv("DATABASE_URL") or os.getenv("METADATA_DB_URL") or "",
            upload_dir=Path(upload_dir) if upload_dir else None,
            chroma_dir=Path(chroma_dir) if chroma_dir else None,
            evaluation_dir=Path(evaluation_dir) if evaluation_dir else None,
            max_upload_mb=_as_int(os.getenv("MAX_UPLOAD_MB"), 25),
            vector_backend=(os.getenv("VECTOR_BACKEND") or os.getenv("VECTOR_STORE") or "auto").lower(),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "hash").lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dimension=_as_int(os.getenv("EMBEDDING_DIMENSION"), 384),
            llm_provider=os.getenv("LLM_PROVIDER", "extractive").lower(),
            llm_model=os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL") or "",
            llm_temperature=_as_float(os.getenv("LLM_TEMPERATURE"), 0.0),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            input_cost_per_million_tokens=_as_float(os.getenv("INPUT_COST_PER_MILLION_TOKENS"), 0.0),
            output_cost_per_million_tokens=_as_float(os.getenv("OUTPUT_COST_PER_MILLION_TOKENS"), 0.0),
            reranker_enabled=_as_bool(os.getenv("RERANKER_ENABLED"), True),
            reranker_model=os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            reranker_top_n=_as_int(os.getenv("RERANKER_TOP_N") or os.getenv("RERANK_TOP_K"), 10),
            retrieval_candidate_k=_as_int(
                os.getenv("RETRIEVAL_CANDIDATE_K") or os.getenv("DENSE_TOP_K") or os.getenv("BM25_TOP_K"),
                20,
            ),
            default_top_k=_as_int(os.getenv("DEFAULT_TOP_K"), 5),
            rrf_k=_as_int(os.getenv("RRF_K"), 60),
            dense_weight=_as_float(os.getenv("DENSE_WEIGHT"), 0.6),
            sparse_weight=_as_float(os.getenv("SPARSE_WEIGHT"), 0.4),
            min_retrieval_score=_as_float(
                os.getenv("MIN_RETRIEVAL_SCORE") or os.getenv("MIN_EVIDENCE_SCORE"), 0.08
            ),
            chunk_size=_as_int(os.getenv("CHUNK_SIZE"), 900),
            chunk_overlap=_as_int(os.getenv("CHUNK_OVERLAP"), 150),
            validation_support_threshold=_as_float(os.getenv("VALIDATION_SUPPORT_THRESHOLD"), 0.45),
            validation_min_coverage=_as_float(os.getenv("VALIDATION_MIN_COVERAGE"), 0.8),
            max_answer_sentences=_as_int(os.getenv("MAX_ANSWER_SENTENCES"), 5),
            prompt_version=os.getenv("PROMPT_VERSION", "grounded-answer-v1"),
            validator_prompt_version=os.getenv("VALIDATOR_PROMPT_VERSION", "claim-validator-v1"),
            retrieval_config_version=os.getenv("RETRIEVAL_CONFIG_VERSION", "hybrid-rrf-v1"),
            mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", ""),
            mlflow_experiment=os.getenv("MLFLOW_EXPERIMENT", "enterprise-knowledge-copilot"),
        )
