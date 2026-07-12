import { afterEach, describe, expect, it, vi } from 'vitest';
import { normalizeCitation, normalizeDocument, normalizeQueryResponse, streamKnowledge } from './client';

afterEach(() => vi.restoreAllMocks());

describe('API response normalization', () => {
  it('normalizes a grounded answer and preserves citation page metadata', () => {
    const result = normalizeQueryResponse({
      answer: 'Employees receive 20 days. [Employee-Handbook.pdf, Page 14]',
      citations: [{
        document_name: 'Employee-Handbook.pdf',
        page_number: 14,
        chunk_id: 'chunk_104',
        quoted_evidence: 'Employees receive 20 annual leave days.',
      }],
      retrieved_passages: [{
        chunk_id: 'chunk_104',
        page_content: 'Employees receive 20 annual leave days.',
        metadata: { document_name: 'Employee-Handbook.pdf', page_number: 14 },
        rerank_score: 0.93,
      }],
      validation: {
        status: 'APPROVED',
        supported_claims: 1,
        unsupported_claims: 0,
        citation_coverage: 1,
      },
      confidence: 92,
    });

    expect(result.answer).toContain('20 days');
    expect(result.citations[0]).toMatchObject({
      document: 'Employee-Handbook.pdf',
      page: 14,
      chunkId: 'chunk_104',
    });
    expect(result.evidence[0].text).toContain('20 annual leave days');
    expect(result.validation.status).toBe('APPROVED');
    expect(result.confidence).toBe(0.92);
  });

  it('keeps the authoritative API answer and exposes validator corrections separately', () => {
    const result = normalizeQueryResponse({
      answer: 'Original unsupported answer.',
      validation_result: {
        status: 'REVISE',
        corrected_answer: 'Corrected grounded answer.',
        reason: 'One claim was unsupported.',
      },
    });

    expect(result.answer).toBe('Original unsupported answer.');
    expect(result.validation.correctedAnswer).toBe('Corrected grounded answer.');
    expect(result.validation.reason).toBe('One claim was unsupported.');
  });

  it('handles alternate document and citation shapes without failing', () => {
    expect(normalizeCitation({ source: 'policy.pdf', metadata: { page: 7 }, text: 'Evidence' })).toMatchObject({
      document: 'policy.pdf', page: 7, quotedEvidence: 'Evidence',
    });
    expect(normalizeDocument({ filename: 'policy.pdf', indexed: true, metadata: { page_count: 12 } })).toMatchObject({
      name: 'policy.pdf', status: 'indexed', pages: 12,
    });
  });

  it('parses named SSE events without leaking protocol labels into the answer', async () => {
    const payload = [
      'event: metadata\ndata: {"query_id":"query-1","experiment":"D"}',
      'event: token\ndata: {"token":"Grounded "}',
      'event: token\ndata: {"token":"answer."}',
      'event: citations\ndata: [{"document":"policy.pdf","page":2,"chunk_id":"c2","quoted_evidence":"Grounded answer."}]',
      'event: validation\ndata: {"status":"APPROVED","supported_claims":1,"unsupported_claims":0,"citation_coverage":1}',
      'event: done\ndata: {"query_id":"query-1","answer":"Grounded answer.","citations":[{"document":"policy.pdf","page":2,"chunk_id":"c2","quoted_evidence":"Grounded answer."}],"validation":{"status":"APPROVED","supported_claims":1,"unsupported_claims":0,"citation_coverage":1}}',
      '',
    ].join('\n\n');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(payload, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    }));
    let streamed = '';

    const result = await streamKnowledge('What is the policy?', {
      onToken: (_, accumulated) => { streamed = accumulated; },
    });

    expect(streamed).toBe('Grounded answer.');
    expect(streamed).not.toContain('event:');
    expect(result.queryId).toBe('query-1');
    expect(result.citations[0].chunkId).toBe('c2');
    expect(result.validation.status).toBe('APPROVED');
  });
});
