import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { Icon } from './Icon';
import { ConfidenceRing, Spinner, formatCost, formatDuration } from './ui';
import { SourcePanel } from './SourcePanel';

const suggestions = [
  { icon: 'library', label: 'Policy details', question: 'What is the annual leave policy and who is eligible?' },
  { icon: 'shield', label: 'Security process', question: 'What steps should I follow to report a security incident?' },
  { icon: 'layers', label: 'Compare documents', question: 'Summarize the remote work requirements across the available policies.' },
];

const experimentOptions = [
  { value: 'A', label: 'A · Dense retrieval' },
  { value: 'B', label: 'B · Hybrid retrieval' },
  { value: 'C', label: 'C · Hybrid + reranker' },
  { value: 'D', label: 'D · Hybrid + validator' },
];

function InlineAnswer({ answer, citations, onCitationClick }) {
  const parts = String(answer || '').split(/(\[[^\]\n]{2,160}\])/g);
  return (
    <div className="answer-text">
      {parts.map((part, index) => {
        const normalized = part.toLowerCase();
        const citation = part.startsWith('[')
          ? citations.find((item) => {
            const document = item.document.toLowerCase();
            const baseName = document.replace(/\.[a-z0-9]+$/i, '');
            const pageMatch = item.page === null || item.page === undefined || normalized.includes(String(item.page));
            return pageMatch && (normalized.includes(document) || normalized.includes(baseName));
          })
          : null;
        if (!citation) return <React.Fragment key={`${index}-${part.slice(0, 12)}`}>{part}</React.Fragment>;
        return (
          <button
            className="inline-citation"
            key={`${citation.id}-${index}`}
            onClick={() => onCitationClick(citation.id)}
            title={`View source: ${citation.document}`}
            type="button"
          >
            {part}
          </button>
        );
      })}
    </div>
  );
}

function FeedbackControls({ message, notify }) {
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const submit = async () => {
    if (!rating || submitting) return;
    setSubmitting(true);
    try {
      await api.submitFeedback({
        query_id: message.result.queryId || message.id,
        helpful: rating === 'positive',
        rating: rating === 'positive' ? 5 : 1,
        comment: comment.trim() || null,
        selected_citation_chunk_id: null,
      });
      setSubmitted(true);
      notify('Thanks — your feedback was recorded.');
    } catch (error) {
      notify(error.message || 'Feedback could not be submitted.', 'danger');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return <span className="feedback-thanks"><Icon name="check" size={14} /> Feedback sent</span>;
  }

  return (
    <div className="feedback-controls">
      <span>Was this grounded and useful?</span>
      <button className={rating === 'positive' ? 'selected' : ''} onClick={() => setRating('positive')} aria-label="Helpful answer" type="button">
        <Icon name="thumbUp" size={15} />
      </button>
      <button className={rating === 'negative' ? 'selected negative' : ''} onClick={() => setRating('negative')} aria-label="Unhelpful answer" type="button">
        <Icon name="thumbDown" size={15} />
      </button>
      {rating && (
        <div className="feedback-detail">
          <input
            aria-label="Optional feedback comment"
            onChange={(event) => setComment(event.target.value)}
            placeholder="Add context (optional)"
            value={comment}
          />
          <button className="small-primary-button" disabled={submitting} onClick={submit} type="button">
            {submitting ? <Spinner size={14} /> : 'Send'}
          </button>
        </div>
      )}
    </div>
  );
}

function AnswerMeta({ result }) {
  const status = result.validation.status;
  const statusLabel = status === 'UNKNOWN' ? 'Not reported' : status.replaceAll('_', ' ');
  return (
    <div className="answer-meta">
      <div className="validation-summary">
        <ConfidenceRing value={result.confidence} />
        <div>
          <span>Answer confidence</span>
          <strong>{result.confidence === null ? 'Not scored' : `${Math.round(result.confidence * 100)}%`}</strong>
        </div>
      </div>
      <div className="meta-divider" />
      <div className="validation-summary">
        <span className={`validation-icon validation-${status.toLowerCase().replaceAll('_', '-')}`}>
          <Icon name={status === 'APPROVED' ? 'check' : status === 'REVISE' ? 'refresh' : status.includes('INSUFFICIENT') ? 'alert' : 'info'} size={16} />
        </span>
        <div>
          <span>Validation</span>
          <strong>{statusLabel}</strong>
        </div>
      </div>
      {result.timings.totalMs !== null && (
        <div className="meta-stat"><Icon name="clock" size={14} /> {formatDuration(result.timings.totalMs)}</div>
      )}
      {result.usage.estimatedCost !== null && (
        <div className="meta-stat"><Icon name="coins" size={14} /> {formatCost(result.usage.estimatedCost)}</div>
      )}
    </div>
  );
}

function AssistantMessage({ message, active, onSelect, onCitationClick, onRetry, notify }) {
  const result = message.result;
  return (
    <article className={`message-row assistant-row ${active ? 'message-active' : ''}`} onClick={onSelect}>
      <div className="assistant-avatar"><Icon name="sparkle" size={17} /></div>
      <div className="message-content">
        <div className="message-author"><strong>Knowledge Copilot</strong><span>Verified assistant</span></div>
        <div className={`answer-card ${message.error ? 'answer-error' : ''}`}>
          {message.error ? (
            <div className="query-error">
              <Icon name="alert" size={20} />
              <div><strong>I couldn’t complete that request</strong><p>{message.error}</p></div>
              <button className="secondary-button" onClick={(event) => { event.stopPropagation(); onRetry(); }} type="button">Try again</button>
            </div>
          ) : message.streaming && !result.answer ? (
            <div className="thinking-state">
              <span className="thinking-orbit"><Icon name="sparkle" size={16} /></span>
              <div><strong>Searching your knowledge base</strong><span>Retrieving, reranking, and validating evidence…</span></div>
            </div>
          ) : (
            <>
              <InlineAnswer answer={result.answer} citations={result.citations} onCitationClick={onCitationClick} />
              {message.streaming && <span className="stream-cursor" />}
              {!message.streaming && result.citations.length > 0 && !result.citations.some((citation) => result.answer.toLowerCase().includes(citation.document.toLowerCase())) && (
                <div className="citation-chips">
                  {result.citations.map((citation, index) => (
                    <button key={citation.id} onClick={(event) => { event.stopPropagation(); onCitationClick(citation.id); }} type="button">
                      <span>{index + 1}</span>{citation.document}{citation.page !== null && ` · p. ${citation.page}`}
                    </button>
                  ))}
                </div>
              )}
              {!message.streaming && <AnswerMeta result={result} />}
              {!message.streaming && result.validation.reason && (
                <div className="validator-note"><Icon name="shield" size={14} /><span>{result.validation.reason}</span></div>
              )}
            </>
          )}
        </div>
        {!message.streaming && !message.error && <FeedbackControls message={message} notify={notify} />}
      </div>
    </article>
  );
}

export function ChatWorkspace({ documentCount, health, onNavigateDocuments, notify }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [experiment, setExperiment] = useState('D');
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [activeCitation, setActiveCitation] = useState(null);
  const scrollRef = useRef(null);
  const abortRef = useRef(null);
  const sessionId = useMemo(
    () => (globalThis.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(36).slice(2)}`),
    [],
  );

  const selectedMessage = messages.find((message) => message.id === selectedMessageId && message.role === 'assistant');

  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const updateMessage = (id, update) => {
    setMessages((current) => current.map((item) => (item.id === id ? { ...item, ...update(item) } : item)));
  };

  const sendQuestion = async (text = question) => {
    const cleanQuestion = text.trim();
    if (!cleanQuestion || busy) return;
    if (health === 'offline') {
      notify('The knowledge service is offline. Check the backend connection.', 'danger');
      return;
    }

    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}`;
    const emptyResult = {
      answer: '', citations: [], evidence: [], confidence: null,
      validation: { status: 'UNKNOWN', reason: '', supportedClaims: 0, unsupportedClaims: 0, citationCoverage: null },
      timings: { totalMs: null, retrievalMs: null, rerankingMs: null, generationMs: null, validationMs: null },
      usage: { inputTokens: 0, outputTokens: 0, totalTokens: 0, estimatedCost: null }, queryId: '',
    };
    setMessages((current) => [
      ...current,
      { id: userId, role: 'user', content: cleanQuestion },
      { id: assistantId, role: 'assistant', question: cleanQuestion, result: emptyResult, streaming: true },
    ]);
    setQuestion('');
    setBusy(true);
    setSelectedMessageId(assistantId);
    setActiveCitation(null);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let gotStreamData = false;
      const result = await api.streamKnowledge(cleanQuestion, {
        sessionId,
        experiment,
        signal: controller.signal,
        onToken: (_, accumulated) => {
          gotStreamData = true;
          updateMessage(assistantId, (message) => ({ result: { ...message.result, answer: accumulated } }));
        },
        onMetadata: (metadata) => {
          gotStreamData = true;
          updateMessage(assistantId, (message) => ({
            result: { ...message.result, ...metadata, answer: metadata.answer || message.result.answer },
          }));
        },
      });
      updateMessage(assistantId, () => ({ result, streaming: false }));
      if (!result.answer && !gotStreamData) throw new Error('The service returned an empty answer.');
    } catch (streamError) {
      if (controller.signal.aborted) return;
      try {
        const result = await api.queryKnowledge(cleanQuestion, { sessionId, experiment, signal: controller.signal });
        if (!result.answer) {
          updateMessage(assistantId, () => ({
            streaming: false,
            error: 'The service returned an empty answer.',
          }));
          return;
        }
        updateMessage(assistantId, () => ({ result, streaming: false }));
      } catch (error) {
        if (!controller.signal.aborted) {
          updateMessage(assistantId, () => ({
            streaming: false,
            error: error.message || streamError.message || 'The query service is unavailable.',
          }));
        }
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const handleCitationClick = (citationId) => {
    setActiveCitation(citationId);
  };

  return (
    <div className="chat-layout">
      <section className="chat-main">
        <div className="chat-toolbar">
          <div className="model-selector">
            <span><Icon name="layers" size={15} /> Retrieval mode</span>
            <select value={experiment} onChange={(event) => setExperiment(event.target.value)} disabled={busy} aria-label="Retrieval experiment">
              {experimentOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <div className="toolbar-context"><Icon name="database" size={15} /> {documentCount} indexed source{documentCount === 1 ? '' : 's'}</div>
        </div>

        <div className="conversation" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="chat-welcome">
              <div className="welcome-mark"><Icon name="sparkle" size={30} /></div>
              <span className="eyebrow">Grounded in your enterprise knowledge</span>
              <h2>What would you like to know?</h2>
              <p>I retrieve from your approved documents, cite the exact passages, and verify each factual claim before answering.</p>
              {documentCount === 0 && (
                <button className="document-warning" onClick={onNavigateDocuments} type="button">
                  <Icon name="alert" size={17} />
                  <span><strong>No documents are indexed yet.</strong> Upload knowledge sources to start asking grounded questions.</span>
                  <Icon name="arrowRight" size={17} />
                </button>
              )}
              <div className="suggestion-grid">
                {suggestions.map((suggestion) => (
                  <button key={suggestion.label} onClick={() => sendQuestion(suggestion.question)} disabled={busy || !documentCount} type="button">
                    <span className="suggestion-icon"><Icon name={suggestion.icon} size={18} /></span>
                    <span><strong>{suggestion.label}</strong><small>{suggestion.question}</small></span>
                    <Icon name="arrowRight" className="suggestion-arrow" size={16} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => message.role === 'user' ? (
                <article className="message-row user-row" key={message.id}>
                  <div className="user-message">{message.content}</div>
                  <div className="mini-avatar">You</div>
                </article>
              ) : (
                <AssistantMessage
                  key={message.id}
                  message={message}
                  active={selectedMessageId === message.id}
                  onSelect={() => { setSelectedMessageId(message.id); setActiveCitation(null); }}
                  onCitationClick={(id) => { setSelectedMessageId(message.id); handleCitationClick(id); }}
                  onRetry={() => sendQuestion(message.question)}
                  notify={notify}
                />
              ))}
            </div>
          )}
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={(event) => { event.preventDefault(); sendQuestion(); }}>
            <textarea
              aria-label="Ask a question"
              disabled={busy}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendQuestion();
                }
              }}
              placeholder="Ask a question about your company knowledge…"
              rows={1}
              value={question}
            />
            <button className="send-button" disabled={!question.trim() || busy} aria-label="Send question" type="submit">
              {busy ? <Spinner size={17} /> : <Icon name="send" size={18} />}
            </button>
          </form>
          <div className="composer-hint"><Icon name="shield" size={13} /> Answers without sufficient evidence are refused automatically.</div>
        </div>
      </section>

      <SourcePanel result={selectedMessage?.result} activeCitation={activeCitation} onCitationSelect={setActiveCitation} />
    </div>
  );
}
