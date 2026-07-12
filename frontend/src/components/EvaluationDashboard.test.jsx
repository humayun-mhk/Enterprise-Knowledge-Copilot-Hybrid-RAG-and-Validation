import { describe, expect, it } from 'vitest';
import { metricFrom, normalizedExperiments } from './EvaluationDashboard';

describe('evaluation result normalization', () => {
  it('maps experiment records to A–D without manufacturing missing metrics', () => {
    const rows = normalizedExperiments({
      experiments: [
        { experiment: 'A', retrieval: { recall_at_5: 0.61, mrr: 0.55 } },
        { experiment: 'D', retrieval: { recall_at_5: 0.82 }, generation: { faithfulness: 0.91 } },
      ],
    });

    expect(rows).toHaveLength(4);
    expect(rows[0].recall5).toBe(0.61);
    expect(rows[1].recall5).toBeNull();
    expect(rows[3].faithfulness).toBe(0.91);
  });

  it('reads numeric metrics from nested reports and value wrappers', () => {
    const report = {
      monitoring: {
        total_queries: { value: 42 },
        latency: { average_latency_ms: 815 },
      },
    };
    expect(metricFrom(report, ['total_queries'])).toBe(42);
    expect(metricFrom(report, ['average_latency_ms'])).toBe(815);
    expect(metricFrom(report, ['hallucination_rate'])).toBeNull();
  });

  it('prefers experiments in the latest measured report over persisted run history', () => {
    const rows = normalizedExperiments({
      results: [{ experiment: 'A', metrics: { recall_at_5: 0.2 } }],
      latest: {
        experiments: [{
          experiment_id: 'D',
          recall_at_5: 0.88,
          hallucination: 0.04,
          total_latency_ms: 1240,
        }],
      },
    });

    expect(rows[0].raw).toBeNull();
    expect(rows[3]).toMatchObject({ recall5: 0.88, hallucinationRate: 0.04, latency: 1240 });
  });
});
