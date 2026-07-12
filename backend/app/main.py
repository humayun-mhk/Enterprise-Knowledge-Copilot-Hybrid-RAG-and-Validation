from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings
from .logging_config import configure_logging
from .schemas import (
    DocumentItem,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    QueryRequest,
    QueryResponse,
    UploadResponse,
    model_dump_compat,
)
from .services.container import AppServices, build_services
from .services.ingestion import SUPPORTED_EXTENSIONS, file_checksum, safe_filename

logger = logging.getLogger(__name__)


def _services(request: Request) -> AppServices:
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application services are not initialized")
    return services


async def _read_upload(upload: Any, max_bytes: int) -> bytes:
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
    return data


def _save_upload(
    services: AppServices,
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filename = safe_filename(filename)
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{extension or 'unknown'}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if not data:
        raise ValueError("Uploaded file is empty")
    checksum = file_checksum(data)
    duplicate = services.database.find_document_by_checksum(checksum)
    if duplicate:
        duplicate["duplicate"] = True
        return duplicate
    document_id = str(uuid.uuid4())
    assert services.settings.upload_dir is not None
    stored_path = services.settings.upload_dir / f"{document_id}__{filename}"
    stored_path.write_bytes(data)
    try:
        return services.database.create_document(
            document_id=document_id,
            document_name=filename,
            content_type=content_type,
            extension=extension,
            stored_path=str(stored_path),
            size_bytes=len(data),
            checksum=checksum,
            metadata={"original_filename": filename, **(metadata or {})},
        )
    except sqlite3.IntegrityError:
        stored_path.unlink(missing_ok=True)
        duplicate = services.database.find_document_by_checksum(checksum)
        if duplicate:
            duplicate["duplicate"] = True
            return duplicate
        raise


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings.from_env()
    configure_logging(configured.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.services = await asyncio.to_thread(build_services, configured)
        logger.info(
            "application_started",
            extra={"version": configured.app_version, **app.state.services.component_backends},
        )
        try:
            yield
        finally:
            app.state.services.close()
            logger.info("application_stopped")

    app = FastAPI(
        title=configured.app_name,
        version=configured.app_version,
        description="Hybrid RAG with citation verification and controlled A-D ablations.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            services = getattr(request.app.state, "services", None)
            if services:
                services.metrics.increment("api_errors")
            logger.exception("request_error", extra={"request_id": request_id, "path": request.url.path})
            raise
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            },
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors(), "error": "validation_error"})

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    async def health(request: Request) -> HealthResponse:
        services = _services(request)
        try:
            services.database.connection.execute("SELECT 1").fetchone()
            database_status = "ready"
        except Exception:
            database_status = "unavailable"
        status = "healthy" if database_status == "ready" else "degraded"
        return HealthResponse(
            status=status,
            version=services.settings.app_version,
            environment=services.settings.environment,
            database=database_status,
            vector_backend=services.vectors.backend_name,
            embedding_provider=services.embeddings.provider_name,
            embedding_model=services.embeddings.model_name,
            bm25_backend=services.bm25.backend_name,
            reranker_backend=services.reranker.backend_name,
            llm_provider=services.settings.llm_provider,
            llm_model=services.settings.llm_model or services.generator.extractive.model_name,
            validator_backend=services.validator.graph_backend,
            indexed_chunks=services.database.count_chunks(),
        )

    @app.post("/documents/upload", response_model=UploadResponse, tags=["documents"])
    async def upload_documents(
        request: Request,
        auto_index: bool = Query(default=False),
    ) -> UploadResponse:
        services = _services(request)
        max_bytes = services.settings.max_upload_mb * 1024 * 1024
        uploaded: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        content_type = request.headers.get("content-type", "")
        metadata: dict[str, Any] = {}
        candidates: list[tuple[str, str | None, bytes]] = []
        if content_type.startswith("multipart/form-data"):
            try:
                form = await request.form()
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not parse multipart form. Ensure python-multipart is installed: {exc}",
                ) from exc
            if form.get("metadata"):
                try:
                    metadata = json.loads(str(form.get("metadata")))
                except json.JSONDecodeError as exc:
                    raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc
                if not isinstance(metadata, dict):
                    raise HTTPException(status_code=400, detail="metadata must be a JSON object")
            for _, value in form.multi_items():
                if hasattr(value, "filename") and hasattr(value, "read"):
                    try:
                        candidates.append(
                            (
                                str(value.filename),
                                getattr(value, "content_type", None),
                                await _read_upload(value, max_bytes),
                            )
                        )
                    except ValueError as exc:
                        errors.append({"filename": str(value.filename), "error": str(exc)})
        else:
            filename = request.headers.get("x-filename")
            if not filename:
                raise HTTPException(
                    status_code=415,
                    detail="Use multipart/form-data with field 'files', or send x-filename for a raw upload.",
                )
            data = await request.body()
            if len(data) > max_bytes:
                raise HTTPException(status_code=413, detail="File exceeds upload limit")
            candidates.append((filename, content_type or None, data))
        if not candidates and not errors:
            raise HTTPException(status_code=400, detail="No files were provided")
        for filename, item_content_type, data in candidates:
            try:
                uploaded.append(
                    await asyncio.to_thread(
                        _save_upload,
                        services,
                        filename=filename,
                        content_type=item_content_type,
                        data=data,
                        metadata=metadata,
                    )
                )
            except ValueError as exc:
                errors.append({"filename": filename, "error": str(exc)})

        indexed = False
        if auto_index and uploaded:
            identifiers = [item["document_id"] for item in uploaded if not item.get("duplicate")]
            if identifiers:
                index_results = await asyncio.to_thread(
                    services.indexing.index, IndexRequest(document_ids=identifiers)
                )
                indexed = all(item.status in {"indexed", "already_indexed"} for item in index_results)
                uploaded = [services.database.get_document(item["document_id"]) or item for item in uploaded]
        services.metrics.increment("documents_uploaded", len(uploaded))
        return UploadResponse(
            documents=[DocumentItem(**item) for item in uploaded],
            indexed=indexed,
            errors=errors,
        )

    @app.post("/documents/index", response_model=IndexResponse, tags=["documents"])
    async def index_documents(payload: IndexRequest, request: Request) -> IndexResponse:
        services = _services(request)
        try:
            results = await asyncio.to_thread(services.indexing.index, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return IndexResponse(
            results=results,
            total_chunks_indexed=sum(item.chunks_indexed for item in results if item.status == "indexed"),
        )

    @app.get("/documents", response_model=list[DocumentItem], tags=["documents"])
    async def list_documents(request: Request, status: str | None = None) -> list[DocumentItem]:
        return [DocumentItem(**item) for item in _services(request).database.list_documents(status)]

    @app.post("/query", response_model=QueryResponse, tags=["rag"])
    async def query(payload: QueryRequest, request: Request) -> QueryResponse:
        services = _services(request)
        if services.database.count_chunks() == 0 and services.vectors.count() == 0:
            # The RAG service itself returns a grounded refusal; this hint keeps the
            # API usable while making the operational cause visible in evidence.
            logger.info("query_with_empty_index")
        return await asyncio.to_thread(services.rag.query, payload)

    @app.post("/query/stream", tags=["rag"])
    async def query_stream(payload: QueryRequest, request: Request) -> StreamingResponse:
        services = _services(request)
        result = await asyncio.to_thread(services.rag.query, payload)

        async def events() -> AsyncIterator[str]:
            yield f"event: metadata\ndata: {json.dumps({'query_id': result.query_id, 'experiment': result.experiment.value})}\n\n"
            words = result.answer.split(" ")
            for index, word in enumerate(words):
                token = word + (" " if index < len(words) - 1 else "")
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0)
            yield f"event: citations\ndata: {json.dumps([model_dump_compat(item) for item in result.citations])}\n\n"
            yield f"event: validation\ndata: {json.dumps(model_dump_compat(result.validation))}\n\n"
            yield f"event: done\ndata: {json.dumps(model_dump_compat(result))}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/metrics", tags=["operations"])
    async def metrics(request: Request) -> dict[str, Any]:
        services = _services(request)
        return services.metrics.snapshot(services.database, components=services.component_backends)

    @app.get("/evaluation/results", tags=["evaluation"])
    async def evaluation_results(request: Request, limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
        services = _services(request)
        results = services.database.list_evaluation_results(limit)
        latest: dict[str, Any] | None = None
        assert services.settings.evaluation_dir is not None
        candidates = [
            services.settings.evaluation_dir / "latest.json",
            services.settings.evaluation_dir / "latest" / "metrics.json",
            Path(__file__).resolve().parents[2] / "evaluation" / "results" / "latest.json",
            Path(__file__).resolve().parents[1] / "evaluation" / "results" / "latest.json",
        ]
        for path in candidates:
            if path.is_file():
                try:
                    latest = json.loads(path.read_text(encoding="utf-8"))
                    break
                except (OSError, json.JSONDecodeError):
                    logger.warning("invalid_evaluation_report", extra={"path": str(path)})
        experiments: list[dict[str, Any]] = []
        if latest and isinstance(latest.get("experiments"), list):
            for row in latest["experiments"]:
                if not isinstance(row, dict):
                    continue
                retrieval_keys = {
                    "recall_at_3": row.get("recall_at_3"),
                    "recall_at_5": row.get("recall_at_5"),
                    "recall_at_10": row.get("recall_at_10"),
                    "mrr": row.get("mrr"),
                    "ndcg": row.get("ndcg_at_10", row.get("ndcg")),
                }
                generation_keys = {
                    "answer_correctness": row.get("answer_correctness"),
                    "faithfulness": row.get("faithfulness"),
                    "citation_precision": row.get("citation_precision"),
                    "citation_coverage": row.get("citation_coverage"),
                    "hallucination_rate": row.get("hallucination", row.get("hallucination_rate")),
                    "unsupported_claim_rate": row.get("unsupported_claim_rate"),
                    "refusal_accuracy": row.get("refusal_correct", row.get("refusal_accuracy")),
                }
                latency_keys = {
                    "average_latency_ms": row.get("total_latency_ms", row.get("average_latency_ms")),
                    "retrieval_latency_ms": row.get("retrieval_latency_ms"),
                }
                cost_keys = {"estimated_cost": row.get("estimated_cost_usd")}
                experiments.append(
                    {
                        "experiment": row.get("experiment_id", row.get("experiment")),
                        "system": row.get("display_name", row.get("system")),
                        "retrieval": {key: value for key, value in retrieval_keys.items() if value is not None},
                        "generation": {key: value for key, value in generation_keys.items() if value is not None},
                        "latency": {key: value for key, value in latency_keys.items() if value is not None},
                        "cost": {key: value for key, value in cost_keys.items() if value is not None},
                    }
                )
        metadata = latest.get("metadata", {}) if isinstance(latest, dict) else {}
        return {
            "dataset_size": metadata.get("question_count") if isinstance(metadata, dict) else None,
            "completed_at": metadata.get("completed_at") if isinstance(metadata, dict) else None,
            "experiments": experiments,
            "runs": results,
            "results": results,
            "latest": latest,
            "has_measured_results": bool(results or latest),
            "message": None if results or latest else "No evaluation run has been recorded yet.",
        }

    @app.post("/feedback", response_model=FeedbackResponse, tags=["feedback"])
    async def feedback(payload: FeedbackRequest, request: Request) -> FeedbackResponse:
        feedback_id = _services(request).database.save_feedback(model_dump_compat(payload))
        return FeedbackResponse(feedback_id=feedback_id)

    return app


app = create_app()
