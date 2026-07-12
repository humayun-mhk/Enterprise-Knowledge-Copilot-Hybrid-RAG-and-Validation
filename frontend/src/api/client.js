const configuredBase = import.meta.env.VITE_API_BASE_URL || '/api';
export const API_BASE_URL = configuredBase.replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

const asArray = (value) => (Array.isArray(value) ? value : []);
const asObject = (value) =>
  value && typeof value === 'object' && !Array.isArray(value) ? value : {};
const firstDefined = (...values) => values.find((value) => value !== undefined && value !== null);

function numeric(value, fallback = null) {
  if (value === '' || value === null || value === undefined) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizeCitation(citation, index = 0) {
  const item = asObject(citation);
  const metadata = asObject(item.metadata);
  return {
    id: String(firstDefined(item.id, item.citation_id, item.chunk_id, metadata.chunk_id, `citation-${index + 1}`)),
    document: String(
      firstDefined(
        item.document,
        item.document_name,
        item.source,
        metadata.document_name,
        metadata.source,
        'Unknown document',
      ),
    ),
    page: firstDefined(item.page, item.page_number, metadata.page, metadata.page_number, null),
    section: String(firstDefined(item.section, metadata.section, '')),
    chunkId: String(firstDefined(item.chunk_id, metadata.chunk_id, item.id, '')),
    quotedEvidence: String(
      firstDefined(
        item.quoted_evidence,
        item.quote,
        item.passage,
        item.chunk_text,
        item.text,
        item.content,
        '',
      ),
    ),
    score: numeric(firstDefined(item.score, item.relevance_score, metadata.score)),
    verified: firstDefined(item.verified, item.is_valid, item.supported, true) !== false,
  };
}

export function normalizeEvidence(evidence, index = 0) {
  const item = asObject(evidence);
  const metadata = asObject(item.metadata);
  return {
    id: String(firstDefined(item.id, item.chunk_id, metadata.chunk_id, `evidence-${index + 1}`)),
    document: String(
      firstDefined(item.document, item.document_name, item.source, metadata.document_name, metadata.source, 'Unknown document'),
    ),
    page: firstDefined(item.page, item.page_number, metadata.page, metadata.page_number, null),
    section: String(firstDefined(item.section, metadata.section, '')),
    chunkId: String(firstDefined(item.chunk_id, metadata.chunk_id, item.id, '')),
    text: String(firstDefined(item.text, item.chunk_text, item.content, item.passage, item.page_content, '')),
    score: numeric(firstDefined(item.reranker_score, item.rerank_score, item.score, item.relevance_score, item.similarity)),
    retrievalMethod: String(firstDefined(item.retrieval_method, item.method, item.source, metadata.retrieval_method, 'retrieved')),
    rank: numeric(firstDefined(item.rank, index + 1), index + 1),
  };
}

export function normalizeQueryResponse(payload) {
  const outer = asObject(payload);
  const result = asObject(firstDefined(outer.data, outer.result, outer.response, outer));
  const validation = asObject(
    firstDefined(result.validation, result.validation_result, result.validator, outer.validation, {}),
  );
  const timings = asObject(firstDefined(result.timings, result.latency, outer.timings, {}));
  const usage = asObject(firstDefined(result.usage, result.token_usage, outer.usage, {}));
  const rawConfidence = numeric(
    firstDefined(result.confidence, validation.confidence, result.groundedness_score),
  );
  const citations = asArray(firstDefined(result.citations, outer.citations, validation.citations)).map(normalizeCitation);
  const evidence = asArray(
    firstDefined(
      result.retrieved_passages,
      result.retrieved_chunks,
      result.evidence,
      result.contexts,
      outer.retrieved_passages,
    ),
  ).map(normalizeEvidence);
  const status = String(
    firstDefined(validation.status, result.validation_status, result.status, 'UNKNOWN'),
  ).toUpperCase();

  return {
    answer: String(
      firstDefined(
        result.answer,
        result.response,
        result.content,
        outer.answer,
        validation.corrected_answer,
        '',
      ),
    ),
    citations,
    evidence,
    validation: {
      status,
      reason: String(firstDefined(validation.reason, validation.message, result.validation_reason, '')),
      supportedClaims: numeric(firstDefined(validation.supported_claims, validation.supportedClaims), 0),
      unsupportedClaims: numeric(firstDefined(validation.unsupported_claims, validation.unsupportedClaims), 0),
      citationCoverage: numeric(firstDefined(validation.citation_coverage, validation.citationCoverage)),
      correctedAnswer: String(firstDefined(validation.corrected_answer, '')),
    },
    confidence: rawConfidence === null ? null : rawConfidence > 1 ? rawConfidence / 100 : rawConfidence,
    timings: {
      totalMs: numeric(firstDefined(timings.total_ms, timings.total, result.latency_ms, result.total_latency_ms)),
      retrievalMs: numeric(firstDefined(timings.retrieval_ms, result.retrieval_latency_ms)),
      rerankingMs: numeric(firstDefined(timings.reranking_ms, result.reranking_latency_ms)),
      generationMs: numeric(firstDefined(timings.generation_ms, result.generation_latency_ms)),
      validationMs: numeric(firstDefined(timings.validation_ms, result.validation_latency_ms)),
    },
    usage: {
      inputTokens: numeric(firstDefined(usage.input_tokens, usage.prompt_tokens), 0),
      outputTokens: numeric(firstDefined(usage.output_tokens, usage.completion_tokens), 0),
      totalTokens: numeric(firstDefined(usage.total_tokens), 0),
      estimatedCost: numeric(firstDefined(usage.estimated_cost_usd, usage.estimated_cost, usage.cost, result.estimated_cost_usd, result.estimated_cost)),
    },
    queryId: String(firstDefined(result.query_id, result.id, outer.query_id, '')),
    raw: payload,
  };
}

export function normalizeDocument(document, index = 0) {
  const item = asObject(document);
  const metadata = asObject(item.metadata);
  return {
    id: String(firstDefined(item.id, item.document_id, metadata.document_id, `document-${index + 1}`)),
    name: String(firstDefined(item.name, item.document_name, item.filename, metadata.document_name, 'Untitled document')),
    type: String(firstDefined(item.type, item.file_type, item.content_type, metadata.file_type, 'document')),
    size: numeric(firstDefined(item.size_bytes, item.size, item.file_size, metadata.file_size)),
    pages: numeric(firstDefined(item.pages, item.page_count, metadata.page_count)),
    chunks: numeric(firstDefined(item.chunks, item.chunk_count, metadata.chunk_count), 0),
    status: String(firstDefined(item.status, item.index_status, item.indexed ? 'indexed' : 'uploaded')).toLowerCase(),
    uploadedAt: firstDefined(item.uploaded_at, item.created_at, item.updated_at, metadata.uploaded_at, null),
    checksum: String(firstDefined(item.checksum, item.content_hash, metadata.checksum, '')),
  };
}

async function parseError(response) {
  const contentType = response.headers.get('content-type') || '';
  try {
    if (contentType.includes('application/json')) {
      const body = await response.json();
      return {
        message: String(firstDefined(body.detail, body.message, body.error, response.statusText)),
        details: body,
      };
    }
    const text = await response.text();
    return { message: text || response.statusText, details: text };
  } catch {
    return { message: response.statusText || 'Request failed', details: null };
  }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('Accept', 'application/json');

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (error) {
    throw new ApiError('Unable to reach the knowledge service.', 0, error);
  }

  if (!response.ok) {
    const error = await parseError(response);
    throw new ApiError(error.message, response.status, error.details);
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function getHealth(options = {}) {
  return request('/health', { signal: options.signal });
}

export async function getDocuments(options = {}) {
  const payload = await request('/documents', { signal: options.signal });
  const source = asObject(payload);
  const documents = Array.isArray(payload)
    ? payload
    : firstDefined(source.documents, source.items, source.data, []);
  return asArray(documents).map(normalizeDocument);
}

export async function uploadDocuments(files, options = {}) {
  const form = new FormData();
  asArray(files).forEach((file) => form.append('files', file, file.name));
  const payload = await request('/documents/upload', {
    method: 'POST',
    body: form,
    signal: options.signal,
  });
  return payload;
}

export async function indexDocuments(documentIds = [], options = {}) {
  return request('/documents/index', {
    method: 'POST',
    body: JSON.stringify({ document_ids: documentIds, force: Boolean(options.force) }),
    signal: options.signal,
  });
}

export async function queryKnowledge(question, options = {}) {
  const payload = await request('/query', {
    method: 'POST',
    body: JSON.stringify({
      question,
      conversation_id: options.sessionId,
      experiment: options.experiment || 'D',
      top_k: options.topK || 8,
      include_evidence: true,
    }),
    signal: options.signal,
  });
  return normalizeQueryResponse(payload);
}

function parseStreamEvent(rawData) {
  const trimmed = rawData.trim();
  if (!trimmed || trimmed === '[DONE]') return trimmed;
  try {
    return JSON.parse(trimmed);
  } catch {
    return { type: 'token', token: rawData };
  }
}

export async function streamKnowledge(question, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/x-ndjson, application/json' },
      body: JSON.stringify({
        question,
        conversation_id: options.sessionId,
        experiment: options.experiment || 'D',
        top_k: options.topK || 8,
        include_evidence: true,
      }),
      signal: options.signal,
    });
  } catch (error) {
    throw new ApiError('Unable to start the answer stream.', 0, error);
  }
  if (!response.ok) {
    const error = await parseError(response);
    throw new ApiError(error.message, response.status, error.details);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    const final = normalizeQueryResponse(await response.json());
    options.onComplete?.(final);
    return final;
  }
  if (!response.body) throw new ApiError('Streaming is not supported by this response.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const isEventStream = contentType.includes('text/event-stream');
  let buffer = '';
  let accumulated = '';
  let latest = {};

  const consume = (rawData, eventName = '') => {
    const event = parseStreamEvent(rawData);
    if (!event || event === '[DONE]') return;
    const type = String(firstDefined(eventName, event?.type, event?.event, '')).toLowerCase();
    if (type === 'error' || event?.error) throw new ApiError(String(event?.error || event?.message || 'The answer stream failed.'));

    if (type === 'citations' && Array.isArray(event)) latest = { ...latest, citations: event };
    if (['evidence', 'retrieved', 'contexts'].includes(type) && Array.isArray(event)) latest = { ...latest, evidence: event };
    if (type === 'validation' && event && !Array.isArray(event)) latest = { ...latest, validation: event };
    if (type === 'metadata' && event && !Array.isArray(event)) latest = { ...latest, ...event };
    if (type === 'done' && event && !Array.isArray(event)) latest = { ...latest, ...event };

    if (typeof event === 'string') {
      if (!type || ['token', 'delta', 'message'].includes(type)) {
        accumulated += event;
        options.onToken?.(event, accumulated);
      }
      return;
    }

    const token = firstDefined(event.token, event.delta, ['token', 'delta', 'message'].includes(type) ? event.content : undefined);
    if (token !== undefined && token !== null) {
      accumulated += String(token);
      options.onToken?.(String(token), accumulated);
    }

    if (!Array.isArray(event) && (event.answer || event.citations || event.retrieved_passages || event.evidence || event.validation)) {
      latest = { ...latest, ...event };
    }
    if (type && type !== 'token') options.onMetadata?.(normalizeQueryResponse({ ...latest, answer: latest.answer || accumulated }));
  };

  const consumeSseBlock = (block) => {
    let eventName = '';
    const data = [];
    block.split(/\r?\n/).forEach((line) => {
      if (line.startsWith('event:')) eventName = line.slice(6).trim();
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    });
    if (data.length) consume(data.join('\n'), eventName);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    if (isEventStream) {
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() || '';
      blocks.forEach(consumeSseBlock);
    } else {
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || '';
      lines.forEach((line) => consume(line));
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    if (isEventStream) consumeSseBlock(buffer);
    else consume(buffer);
  }

  const final = normalizeQueryResponse({ ...latest, answer: latest.answer || accumulated });
  options.onComplete?.(final);
  return final;
}

export async function getMetrics(options = {}) {
  return request('/metrics', { signal: options.signal });
}

export async function getEvaluationResults(options = {}) {
  return request('/evaluation/results', { signal: options.signal });
}

export async function submitFeedback(feedback, options = {}) {
  return request('/feedback', {
    method: 'POST',
    body: JSON.stringify(feedback),
    signal: options.signal,
  });
}

export const api = {
  getHealth,
  getDocuments,
  uploadDocuments,
  indexDocuments,
  queryKnowledge,
  streamKnowledge,
  getMetrics,
  getEvaluationResults,
  submitFeedback,
};
