import { useEffect, useState } from 'react';
import { Icon } from './Icon';
import { EmptyState, formatPercent } from './ui';

function SourceLocation({ item }) {
  return (
    <span className="source-location">
      {item.document}
      {item.page !== null && item.page !== undefined && ` · Page ${item.page}`}
      {item.section && ` · ${item.section}`}
    </span>
  );
}

function CitationCard({ citation, index, active, onSelect }) {
  return (
    <article className={`source-card citation-card ${active ? 'source-card-active' : ''}`} id={`citation-${citation.id}`}>
      <button className="source-card-header" type="button" onClick={() => onSelect?.(citation.id)}>
        <span className="source-index">{index + 1}</span>
        <div>
          <strong>{citation.document}</strong>
          <small>
            {citation.page !== null && citation.page !== undefined ? `Page ${citation.page}` : 'Page unavailable'}
            {citation.section ? ` · ${citation.section}` : ''}
          </small>
        </div>
        <span className={`verification-mark ${citation.verified ? 'verified' : 'unverified'}`} title={citation.verified ? 'Citation verified' : 'Citation not verified'}>
          <Icon name={citation.verified ? 'check' : 'alert'} size={14} />
        </span>
      </button>
      {citation.quotedEvidence ? (
        <blockquote>“{citation.quotedEvidence}”</blockquote>
      ) : (
        <p className="evidence-unavailable">No quoted passage was returned.</p>
      )}
      <div className="source-card-footer">
        {citation.chunkId && <code>{citation.chunkId}</code>}
        {citation.score !== null && <span>Relevance {citation.score >= 0 && citation.score <= 1 ? formatPercent(citation.score) : citation.score.toFixed(3)}</span>}
      </div>
    </article>
  );
}

function EvidenceCard({ evidence, index }) {
  const [expanded, setExpanded] = useState(false);
  const long = evidence.text.length > 310;
  const text = long && !expanded ? `${evidence.text.slice(0, 310).trim()}…` : evidence.text;
  return (
    <article className="source-card evidence-card">
      <div className="source-card-header static">
        <span className="rank-badge">#{evidence.rank || index + 1}</span>
        <div>
          <strong>{evidence.document}</strong>
          <small>{evidence.page !== null && evidence.page !== undefined ? `Page ${evidence.page}` : 'Page unavailable'}</small>
        </div>
        {evidence.score !== null && (
          <span className="score-pill">
            {evidence.score >= 0 && evidence.score <= 1 ? formatPercent(evidence.score, 0) : evidence.score.toFixed(2)}
          </span>
        )}
      </div>
      {evidence.section && <span className="section-label">{evidence.section}</span>}
      <p className="evidence-text">{text || 'Passage text was not returned by the service.'}</p>
      {long && (
        <button className="text-button" onClick={() => setExpanded((value) => !value)} type="button">
          {expanded ? 'Show less' : 'Read full passage'}
        </button>
      )}
      <div className="source-card-footer">
        <span className="method-tag">{evidence.retrievalMethod.replaceAll('_', ' ')}</span>
        {evidence.chunkId && <code>{evidence.chunkId}</code>}
      </div>
    </article>
  );
}

export function SourcePanel({ result, activeCitation, onCitationSelect }) {
  const [tab, setTab] = useState('citations');
  const citations = result?.citations || [];
  const evidence = result?.evidence || [];

  const visibleTab = activeCitation ? 'citations' : tab;

  useEffect(() => {
    if (!activeCitation) return;
    const timer = window.setTimeout(() => {
      document.getElementById(`citation-${activeCitation}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [activeCitation]);

  return (
    <aside className="source-panel" aria-label="Answer evidence">
      <div className="source-panel-heading">
        <div>
          <span className="eyebrow"><Icon name="shield" size={14} /> Verification trace</span>
          <h2>Sources & evidence</h2>
        </div>
        {result?.validation?.status && result.validation.status !== 'UNKNOWN' && (
          <span className={`validation-seal seal-${result.validation.status.toLowerCase().replaceAll('_', '-')}`}>
            <Icon name={result.validation.status === 'APPROVED' ? 'check' : result.validation.status === 'REVISE' ? 'refresh' : 'alert'} size={14} />
            {result.validation.status.replaceAll('_', ' ')}
          </span>
        )}
      </div>

      <div className="source-tabs" role="tablist" aria-label="Evidence views">
        <button className={visibleTab === 'citations' ? 'active' : ''} onClick={() => setTab('citations')} role="tab" aria-selected={visibleTab === 'citations'} type="button">
          Citations <span>{citations.length}</span>
        </button>
        <button className={visibleTab === 'evidence' ? 'active' : ''} onClick={() => { setTab('evidence'); onCitationSelect?.(null); }} role="tab" aria-selected={visibleTab === 'evidence'} type="button">
          Retrieved <span>{evidence.length}</span>
        </button>
      </div>

      <div className="source-panel-content">
        {!result ? (
          <EmptyState
            icon="quote"
            title="Evidence will appear here"
            description="Ask a question, then inspect every citation and retrieved passage used in the answer."
          />
        ) : visibleTab === 'citations' ? (
          citations.length ? citations.map((citation, index) => (
            <CitationCard
              citation={citation}
              index={index}
              key={citation.id}
              active={activeCitation === citation.id}
              onSelect={onCitationSelect}
            />
          )) : (
            <EmptyState
              icon="quote"
              title="No citations returned"
              description="The service did not attach citation metadata to this answer. Treat it as unverified."
            />
          )
        ) : evidence.length ? evidence.map((item, index) => (
          <EvidenceCard evidence={item} index={index} key={item.id} />
        )) : (
          <EmptyState
            icon="search"
            title="No retrieved passages"
            description="Retrieval evidence was not included in this response."
          />
        )}
      </div>
    </aside>
  );
}

export { SourceLocation };
