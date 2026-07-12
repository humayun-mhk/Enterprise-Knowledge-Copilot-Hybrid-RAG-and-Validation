from __future__ import annotations

import hashlib
import uuid

from app.db import Database
from app.schemas import IndexRequest
from app.services.bm25 import BM25Index
from app.services.embeddings import HashEmbeddingService
from app.services.indexing import IndexingService
from app.services.vector_store import InMemoryVectorStore


def test_database_migrations_and_indexing(settings) -> None:
    settings.ensure_directories()
    database = Database(settings.sqlite_path)
    database.initialize()
    source = settings.upload_dir / "policy.txt"
    data = b"Annual Leave\nFull-time employees receive 20 paid annual leave days per calendar year."
    source.write_bytes(data)
    document_id = str(uuid.uuid4())
    database.create_document(
        document_id=document_id,
        document_name="policy.txt",
        content_type="text/plain",
        extension=".txt",
        stored_path=str(source),
        size_bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
    )
    vectors = InMemoryVectorStore()
    sparse = BM25Index()
    service = IndexingService(settings, database, HashEmbeddingService(128), vectors, sparse)
    results = service.index(IndexRequest(document_ids=[document_id]))
    assert results[0].status == "indexed"
    assert database.count_chunks() == 1
    assert vectors.count() == 1
    assert sparse.search("annual leave", top_k=1)[0].chunk.document_name == "policy.txt"
    assert database.list_documents()[0]["metadata"]["embedding_provider"] == "hash"
    database.close()


def test_operational_metrics_do_not_invent_queries(settings) -> None:
    settings.ensure_directories()
    database = Database(settings.sqlite_path)
    database.initialize()
    metrics = database.operational_metrics()
    assert metrics["total_queries"] == 0
    assert metrics["average_latency_ms"] == 0
    database.close()

