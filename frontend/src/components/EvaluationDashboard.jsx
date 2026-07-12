import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { Icon } from './Icon';
import { EmptyState, MetricCard, Spinner, formatCost, formatDuration, formatNumber, formatPercent } from './ui';

const experimentDefinitions = [
  { id: 'A', name: 'Dense RAG', description: 'Dense vector retrieval only' },
  { id: 'B', name: 'Hybrid RAG', description: 'Dense + BM25 retrieval' },
  { id: 'C', name: 'Hybrid + Reranker', description: 'RRF fusion + configured reranker' },
  { id: 'D', name: 'Hybrid + Validator', description: 'Citations + validation agent' },
];

const keyOf = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');

function flattenMetrics(value, result = new Map(), prefix = '') {
  if (!value || typeof value !== 'object') return result;
  Object.entries(value).forEach(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof item === 'number' && Number.isFinite(item)) {
      result.set(keyOf(path), item);
      result.set(keyOf(key), item);
    } else if (item && typeof item === 'object') {
      if (typeof item.value === 'number') {
        result.set(keyOf(path), item.value);
        result.set(keyOf(key), item.value);
      }
      flattenMetrics(item, result, path);
    }
  });
  return result;
}

function metricFrom(value, aliases) {
  const flat = flattenMetrics(value);
  for (const alias of aliases) {
    const exact = flat.get(keyOf(alias));
    if (exact !== undefined) return exact;
  }
  for (const alias of aliases) {
    const target = keyOf(alias);
    const match = [...flat.entries()].find(([key]) => key.endsWith(target));
    if (match) return match[1];
  }
  return null;
}

function extractExperimentSource(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object') return [];
  for (const key of ['experiments', 'systems']) {
    if (Array.isArray(payload[key]) && payload[key].length) return payload[key];
    if (payload[key] && typeof payload[key] === 'object') {
      return Object.entries(payload[key]).map(([id, value]) => ({ experiment: id, ...value }));
    }
  }
  if (payload.latest && typeof payload.latest === 'object') {
    const latest = extractExperimentSource(payload.latest);
    if (latest.length) return latest;
  }
  for (const key of ['results', 'comparison', 'runs']) {
    if (Array.isArray(payload[key]) && payload[key].length) return payload[key];
    if (payload[key] && typeof payload[key] === 'object') {
      return Object.entries(payload[key]).map(([id, value]) => ({ experiment: id, ...value }));
    }
  }
  if (['A', 'B', 'C', 'D'].some((key) => payload[key])) {
    return Object.entries(payload).filter(([key]) => ['A', 'B', 'C', 'D'].includes(key.toUpperCase())).map(([id, value]) => ({ experiment: id, ...value }));
  }
  return [];
}

function identifyExperiment(item) {
  const source = keyOf(item.experiment || item.experiment_id || item.system || item.name || item.version);
  if (['a', 'experimenta', 'dense', 'denserag'].includes(source) || source.includes('denseonly')) return 'A';
  if (['b', 'experimentb', 'hybrid', 'hybridrag'].includes(source)) return 'B';
  if (['c', 'experimentc'].includes(source) || source.includes('rerank')) return 'C';
  if (['d', 'experimentd'].includes(source) || source.includes('validat')) return 'D';
  return String(item.experiment || item.experiment_id || '').toUpperCase();
}

function normalizedExperiments(payload) {
  const source = extractExperimentSource(payload);
  return experimentDefinitions.map((definition) => {
    const raw = source.find((item) => identifyExperiment(item) === definition.id) || null;
    return {
      ...definition,
      raw,
      recall3: raw ? metricFrom(raw, ['recall_at_3', 'recall3']) : null,
      recall5: raw ? metricFrom(raw, ['recall_at_5', 'recall5']) : null,
      recall10: raw ? metricFrom(raw, ['recall_at_10', 'recall10']) : null,
      mrr: raw ? metricFrom(raw, ['mean_reciprocal_rank', 'mrr']) : null,
      ndcg: raw ? metricFrom(raw, ['ndcg_at_10', 'ndcg_at_5', 'ndcg']) : null,
      correctness: raw ? metricFrom(raw, ['answer_correctness', 'correctness']) : null,
      faithfulness: raw ? metricFrom(raw, ['faithfulness']) : null,
      citationPrecision: raw ? metricFrom(raw, ['citation_precision']) : null,
      hallucinationRate: raw ? metricFrom(raw, ['hallucination_rate', 'hallucination']) : null,
      latency: raw ? metricFrom(raw, ['total_latency_ms', 'average_latency_ms', 'avg_latency_ms', 'latency_ms', 'average_latency']) : null,
      cost: raw ? metricFrom(raw, ['estimated_cost_usd', 'estimated_cost', 'average_cost', 'avg_cost']) : null,
    };
  });
}

function deltaFor(rows, index, key) {
  if (index === 0) return null;
  const current = rows[index][key];
  const previous = rows[index - 1][key];
  if (current === null || previous === null) return null;
  return current - previous;
}

function MetricCell({ value, format, delta, lowerIsBetter = false }) {
  if (value === null || value === undefined) return <span className="no-value">—</span>;
  const improved = delta !== null && (lowerIsBetter ? delta < 0 : delta > 0);
  const worsened = delta !== null && (lowerIsBetter ? delta > 0 : delta < 0);
  return (
    <div className="comparison-value">
      <strong>{format(value)}</strong>
      {delta !== null && (
        <small className={improved ? 'delta-good' : worsened ? 'delta-bad' : 'delta-flat'} title="Change from the previous experiment">
          {delta > 0 ? '+' : ''}{format(delta)}
        </small>
      )}
    </div>
  );
}

function QualityBars({ rows }) {
  const available = rows.filter((row) => row.raw && (row.recall5 !== null || row.mrr !== null));
  if (!available.length) {
    return <EmptyState icon="chart" title="No retrieval scores yet" description="Complete an evaluation run to populate Recall@5 and MRR." />;
  }
  return (
    <div className="quality-chart">
      <div className="chart-legend"><span><i className="legend-recall" /> Recall@5</span><span><i className="legend-mrr" /> MRR</span></div>
      {available.map((row) => (
        <div className="quality-row" key={row.id}>
          <div className="quality-label"><strong>{row.id}</strong><span>{row.name}</span></div>
          <div className="quality-bars">
            <div className="bar-track"><div className="bar-fill recall-fill" style={{ width: `${Math.max(0, Math.min(100, (row.recall5 || 0) * (row.recall5 > 1 ? 1 : 100)))}%` }} /><span>{formatPercent(row.recall5)}</span></div>
            <div className="bar-track"><div className="bar-fill mrr-fill" style={{ width: `${Math.max(0, Math.min(100, (row.mrr || 0) * (row.mrr > 1 ? 1 : 100)))}%` }} /><span>{row.mrr === null ? '—' : Number(row.mrr).toFixed(3)}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function findMetadata(payload, aliases) {
  return metricFrom(payload, aliases);
}

export function EvaluationDashboard({ notify }) {
  const [metrics, setMetrics] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    const [metricsResult, evaluationResult] = await Promise.allSettled([
      api.getMetrics(),
      api.getEvaluationResults(),
    ]);
    if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value);
    if (evaluationResult.status === 'fulfilled') setEvaluation(evaluationResult.value);
    if (metricsResult.status === 'rejected' && evaluationResult.status === 'rejected') {
      setError(evaluationResult.reason?.message || 'Evaluation results are unavailable.');
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const rows = useMemo(() => normalizedExperiments(evaluation), [evaluation]);
  const hasEvaluation = rows.some((row) => row.raw);
  const totalQueries = findMetadata(metrics, ['total_queries', 'query_count']);
  const averageLatency = findMetadata(metrics, ['average_answer_latency_ms', 'avg_total_latency_ms', 'average_latency_ms', 'avg_latency_ms']);
  const retrievalLatency = findMetadata(metrics, ['average_retrieval_latency_ms', 'avg_retrieval_latency_ms', 'retrieval_latency_ms']);
  const citationCoverage = findMetadata(metrics, ['average_citation_coverage', 'citation_coverage']);
  const totalCost = findMetadata(metrics, ['estimated_cost_usd', 'estimated_cost', 'total_estimated_cost_usd', 'total_estimated_cost', 'total_cost']);
  const tokenUsage = findMetadata(metrics, ['total_token_usage', 'total_tokens', 'token_usage']);
  const validationFailures = findMetadata(metrics, ['validation_failures']);
  const refusals = findMetadata(metrics, ['insufficient_evidence_responses', 'insufficient_evidence_count', 'refusals']);
  const lowConfidence = findMetadata(metrics, ['low_confidence_answers', 'low_confidence_count']);
  const apiErrors = findMetadata(metrics, ['api_errors', 'error_count']);
  const datasetSize = findMetadata(evaluation, ['dataset_size', 'question_count', 'total_questions', 'samples']);
  const latestMetadata = evaluation?.latest?.metadata || {};
  const adapterMetadata = latestMetadata.adapter || {};
  const isOfflineBaseline = adapterMetadata.offline === true;
  const lastRun = evaluation?.completed_at || evaluation?.last_run_at || evaluation?.generated_at || evaluation?.timestamp || latestMetadata.completed_at || latestMetadata.generated_at || null;

  const exportResults = () => {
    if (!evaluation) return;
    const blob = new Blob([JSON.stringify(evaluation, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `rag-evaluation-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    notify('Evaluation results exported.');
  };

  return (
    <div className="evaluation-page">
      <div className="evaluation-actions">
        <div className="run-context">
          <span className="run-icon"><Icon name="chart" size={18} /></span>
          <div><strong>{hasEvaluation ? 'Latest benchmark run' : 'Evaluation pipeline'}</strong><small>{lastRun ? `Completed ${new Date(lastRun).toLocaleString()}` : 'Waiting for a completed benchmark run'}</small></div>
          {datasetSize !== null && <span className="sample-count">{formatNumber(datasetSize)} questions</span>}
        </div>
        <div>
          <button className="secondary-button" onClick={load} disabled={loading} type="button">{loading ? <Spinner size={15} /> : <Icon name="refresh" size={15} />} Refresh</button>
          <button className="primary-button" onClick={exportResults} disabled={!evaluation} type="button"><Icon name="external" size={15} /> Export results</button>
        </div>
      </div>

      {error && <div className="page-alert"><Icon name="alert" size={18} /><div><strong>Couldn’t load evaluation data</strong><p>{error}</p></div></div>}

      {hasEvaluation && isOfflineBaseline && (
        <div className="page-alert provenance-alert">
          <Icon name="info" size={18} />
          <div>
            <strong>Offline fallback baseline</strong>
            <p>
              Measured with {adapterMetadata.embedding_model || 'local hash embeddings'}, {' '}
              {adapterMetadata.bm25_backend || 'BM25'}, {adapterMetadata.reranker_backend || 'fallback reranking'}, and {' '}
              {adapterMetadata.llm_provider || 'extractive'} generation. These are not learned cross-encoder or hosted-LLM scores.
            </p>
          </div>
        </div>
      )}

      <section className="metrics-grid monitoring-grid">
        <MetricCard icon="chat" label="Total queries" value={formatNumber(totalQueries)} detail="Since metrics reset" tone="blue" loading={loading} />
        <MetricCard icon="clock" label="Avg. answer latency" value={formatDuration(averageLatency)} detail={retrievalLatency !== null ? `${formatDuration(retrievalLatency)} retrieval` : 'Retrieval timing unavailable'} tone="violet" loading={loading} />
        <MetricCard icon="quote" label="Citation coverage" value={formatPercent(citationCoverage)} detail="Claims with supporting citations" tone="green" loading={loading} />
        <MetricCard icon="coins" label="Estimated cost" value={formatCost(totalCost)} detail={tokenUsage !== null ? `${formatNumber(tokenUsage)} tokens` : 'Token usage unavailable'} tone="amber" loading={loading} />
      </section>

      <section className="comparison-section panel-card">
        <div className="section-heading comparison-heading">
          <div><span className="eyebrow">Experiment comparison</span><h2>RAG system performance</h2><p>Every value below comes from the latest evaluation output. Deltas compare each system with the preceding version.</p></div>
          <span className="measured-badge"><Icon name="shield" size={14} /> Measured results only</span>
        </div>
        {loading ? (
          <div className="table-loading"><Spinner /><span>Loading experiment results…</span></div>
        ) : !hasEvaluation ? (
          <EmptyState
            icon="chart"
            title="No completed evaluation run"
            description="Run the benchmark pipeline to compare Dense RAG, Hybrid RAG, reranking, and validation. This dashboard never fabricates placeholder scores."
          />
        ) : (
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead><tr><th>System</th><th>Recall@5</th><th>MRR</th><th>Correctness</th><th>Faithfulness</th><th>Citation precision</th><th>Hallucination rate</th><th>Latency</th></tr></thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.id} className={row.id === 'D' ? 'highlight-row' : ''}>
                    <td><div className="system-name"><span>{row.id}</span><div><strong>{row.name}</strong><small>{row.description}</small></div></div></td>
                    <td><MetricCell value={row.recall5} delta={deltaFor(rows, index, 'recall5')} format={formatPercent} /></td>
                    <td><MetricCell value={row.mrr} delta={deltaFor(rows, index, 'mrr')} format={(value) => Number(value).toFixed(3)} /></td>
                    <td><MetricCell value={row.correctness} delta={deltaFor(rows, index, 'correctness')} format={formatPercent} /></td>
                    <td><MetricCell value={row.faithfulness} delta={deltaFor(rows, index, 'faithfulness')} format={formatPercent} /></td>
                    <td><MetricCell value={row.citationPrecision} delta={deltaFor(rows, index, 'citationPrecision')} format={formatPercent} /></td>
                    <td><MetricCell value={row.hallucinationRate} delta={deltaFor(rows, index, 'hallucinationRate')} format={formatPercent} lowerIsBetter /></td>
                    <td><MetricCell value={row.latency} delta={deltaFor(rows, index, 'latency')} format={formatDuration} lowerIsBetter /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="evaluation-lower-grid">
        <section className="panel-card quality-panel">
          <div className="card-heading"><div><h2>Retrieval quality</h2><p>Recall@5 and mean reciprocal rank by version.</p></div><Icon name="trend" size={19} /></div>
          {loading ? <div className="table-loading compact"><Spinner /></div> : <QualityBars rows={rows} />}
        </section>

        <section className="panel-card health-panel">
          <div className="card-heading"><div><h2>Quality guardrails</h2><p>Live counters from production monitoring.</p></div><Icon name="shield" size={19} /></div>
          <div className="guardrail-list">
            <div><span className="guardrail-icon red"><Icon name="xCircle" size={17} /></span><span><strong>Validation failures</strong><small>Rejected or failed validation checks</small></span><b>{formatNumber(validationFailures)}</b></div>
            <div><span className="guardrail-icon amber"><Icon name="alert" size={17} /></span><span><strong>Insufficient evidence</strong><small>Safe refusals returned to users</small></span><b>{formatNumber(refusals)}</b></div>
            <div><span className="guardrail-icon violet"><Icon name="gauge" size={17} /></span><span><strong>Low-confidence answers</strong><small>Responses below confidence threshold</small></span><b>{formatNumber(lowConfidence)}</b></div>
            <div><span className="guardrail-icon blue"><Icon name="bolt" size={17} /></span><span><strong>API errors</strong><small>Failed requests observed</small></span><b>{formatNumber(apiErrors)}</b></div>
          </div>
        </section>
      </div>
    </div>
  );
}

export { metricFrom, normalizedExperiments };
