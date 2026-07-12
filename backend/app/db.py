from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from .domain import ChunkRecord


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            document_name TEXT NOT NULL,
            content_type TEXT,
            extension TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            checksum TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'uploaded',
            page_count INTEGER NOT NULL DEFAULT 0,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TEXT NOT NULL,
            indexed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            document_name TEXT NOT NULL,
            page_number INTEGER,
            section TEXT,
            chunk_text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            embedding_json TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(document_id, content_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);

        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id TEXT PRIMARY KEY,
            query_id TEXT NOT NULL,
            rating INTEGER,
            helpful INTEGER,
            comment TEXT,
            selected_citation_chunk_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query_id);

        CREATE TABLE IF NOT EXISTS query_events (
            query_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            experiment TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            citation_coverage REAL NOT NULL,
            retrieval_ms REAL NOT NULL,
            total_ms REAL NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            estimated_cost_usd REAL NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_query_events_created ON query_events(created_at);

        CREATE TABLE IF NOT EXISTS evaluation_results (
            run_id TEXT PRIMARY KEY,
            experiment TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            dataset_version TEXT,
            metrics_json TEXT NOT NULL,
            config_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evaluation_experiment ON evaluation_results(experiment, created_at);
        """,
    ),
]


class Database:
    """Small SQLite repository used for metadata and operational telemetry.

    Chroma remains the production vector index; storing embeddings here makes the
    in-memory fallback restart-safe and keeps tests deterministic.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.connection
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def initialize(self) -> None:
        with self.transaction() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for version, sql in MIGRATIONS:
                if version not in applied:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, utc_now()),
                    )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    @staticmethod
    def _document(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item.pop("stored_path", None)
        item.pop("extension", None)
        item.pop("error", None)
        item["duplicate"] = False
        return item

    def create_document(
        self,
        *,
        document_id: str,
        document_name: str,
        content_type: str | None,
        extension: str,
        stored_path: str,
        size_bytes: int,
        checksum: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created = utc_now()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO documents(
                    document_id, document_name, content_type, extension, stored_path,
                    size_bytes, checksum, status, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
                """,
                (
                    document_id,
                    document_name,
                    content_type,
                    extension,
                    stored_path,
                    size_bytes,
                    checksum,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created,
                ),
            )
        result = self.get_document(document_id, include_private=False)
        assert result is not None
        return result

    def find_document_by_checksum(self, checksum: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM documents WHERE checksum=?", (checksum,)).fetchone()
        return self._document(row)

    def get_document(self, document_id: str, *, include_private: bool = False) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if row is None:
            return None
        if not include_private:
            return self._document(row)
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item["duplicate"] = False
        return item

    def list_documents(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.connection.execute(
                "SELECT * FROM documents WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.connection.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [item for row in rows if (item := self._document(row)) is not None]

    def set_document_status(
        self,
        document_id: str,
        status: str,
        *,
        page_count: int | None = None,
        chunk_count: int | None = None,
        error: str | None = None,
    ) -> None:
        fields = ["status=?", "error=?"]
        values: list[Any] = [status, error]
        if page_count is not None:
            fields.append("page_count=?")
            values.append(page_count)
        if chunk_count is not None:
            fields.append("chunk_count=?")
            values.append(chunk_count)
        if status == "indexed":
            fields.append("indexed_at=?")
            values.append(utc_now())
        values.append(document_id)
        with self.transaction() as conn:
            conn.execute(f"UPDATE documents SET {', '.join(fields)} WHERE document_id=?", values)

    def update_document_metadata(self, document_id: str, metadata: dict[str, Any]) -> None:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT metadata_json FROM documents WHERE document_id=?", (document_id,)
            ).fetchone()
            existing = json.loads(row[0] or "{}") if row else {}
            existing.update(metadata)
            conn.execute(
                "UPDATE documents SET metadata_json=? WHERE document_id=?",
                (json.dumps(existing, ensure_ascii=False), document_id),
            )

    def delete_chunks_for_document(self, document_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))

    def save_chunks(self, chunks: Sequence[ChunkRecord], *, replace_document_id: str | None = None) -> tuple[int, int]:
        inserted = 0
        duplicates = 0
        with self.transaction() as conn:
            if replace_document_id:
                conn.execute("DELETE FROM chunks WHERE document_id=?", (replace_document_id,))
            for chunk in chunks:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO chunks(
                        chunk_id, document_id, document_name, page_number, section,
                        chunk_text, content_hash, metadata_json, embedding_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.document_name,
                        chunk.page_number,
                        chunk.section,
                        chunk.chunk_text,
                        chunk.content_hash,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                        utc_now(),
                    ),
                )
                if cursor.rowcount:
                    inserted += 1
                else:
                    duplicates += 1
        return inserted, duplicates

    @staticmethod
    def _chunk(row: sqlite3.Row) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            document_name=row["document_name"],
            page_number=row["page_number"],
            section=row["section"],
            chunk_text=row["chunk_text"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            embedding=json.loads(row["embedding_json"]) if row["embedding_json"] else None,
            content_hash=row["content_hash"],
        )

    def list_chunks(self, document_ids: Sequence[str] | None = None) -> list[ChunkRecord]:
        if document_ids:
            placeholders = ",".join("?" for _ in document_ids)
            rows = self.connection.execute(
                f"SELECT * FROM chunks WHERE document_id IN ({placeholders}) ORDER BY document_id, rowid",
                list(document_ids),
            ).fetchall()
        else:
            rows = self.connection.execute("SELECT * FROM chunks ORDER BY document_id, rowid").fetchall()
        return [self._chunk(row) for row in rows]

    def count_chunks(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def record_query(self, event: dict[str, Any]) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO query_events(
                    query_id, question, experiment, status, confidence, citation_coverage,
                    retrieval_ms, total_ms, prompt_tokens, completion_tokens,
                    estimated_cost_usd, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["query_id"],
                    event.get("question", ""),
                    event.get("experiment", "D"),
                    event.get("status", "UNKNOWN"),
                    float(event.get("confidence", 0)),
                    float(event.get("citation_coverage", 0)),
                    float(event.get("retrieval_ms", 0)),
                    float(event.get("total_ms", 0)),
                    int(event.get("prompt_tokens", 0)),
                    int(event.get("completion_tokens", 0)),
                    float(event.get("estimated_cost_usd", 0)),
                    event.get("error"),
                    utc_now(),
                ),
            )

    def save_feedback(self, data: dict[str, Any]) -> str:
        feedback_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO feedback(
                    feedback_id, query_id, rating, helpful, comment,
                    selected_citation_chunk_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    data["query_id"],
                    data.get("rating"),
                    None if data.get("helpful") is None else int(bool(data["helpful"])),
                    data.get("comment"),
                    data.get("selected_citation_chunk_id"),
                    utc_now(),
                ),
            )
        return feedback_id

    def operational_metrics(self) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_queries,
                COALESCE(AVG(total_ms), 0) AS average_latency_ms,
                COALESCE(AVG(retrieval_ms), 0) AS average_retrieval_latency_ms,
                COALESCE(SUM(CASE WHEN status='INSUFFICIENT_EVIDENCE' THEN 1 ELSE 0 END), 0) AS insufficient_evidence_responses,
                COALESCE(SUM(CASE WHEN status='REVISE' THEN 1 ELSE 0 END), 0) AS validation_failures,
                COALESCE(SUM(CASE WHEN confidence < 0.5 THEN 1 ELSE 0 END), 0) AS low_confidence_answers,
                COALESCE(AVG(citation_coverage), 0) AS average_citation_coverage,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd,
                COALESCE(SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END), 0) AS api_errors
            FROM query_events
            """
        ).fetchone()
        feedback = self.connection.execute(
            """
            SELECT COUNT(*) AS feedback_count, COALESCE(AVG(rating), 0) AS average_rating,
                   COALESCE(AVG(helpful), 0) AS helpful_rate FROM feedback
            """
        ).fetchone()
        output = dict(row)
        output.update(dict(feedback))
        output["indexed_documents"] = int(
            self.connection.execute("SELECT COUNT(*) FROM documents WHERE status='indexed'").fetchone()[0]
        )
        output["indexed_chunks"] = self.count_chunks()
        return output

    def save_evaluation_result(
        self,
        *,
        run_id: str,
        experiment: str,
        dataset_name: str,
        dataset_version: str | None,
        metrics: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_results(
                    run_id, experiment, dataset_name, dataset_version,
                    metrics_json, config_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    experiment,
                    dataset_name,
                    dataset_version,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(config or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )

    def list_evaluation_results(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM evaluation_results ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 1000)),)
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "experiment": row["experiment"],
                "dataset_name": row["dataset_name"],
                "dataset_version": row["dataset_version"],
                "metrics": json.loads(row["metrics_json"]),
                "config": json.loads(row["config_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
