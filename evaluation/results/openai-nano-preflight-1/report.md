# Measured experiment results

These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dense RAG | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 2647.2510 |
| Hybrid RAG | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1315.1500 |
| Hybrid + Reranker | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 38832.9890 |
| Hybrid + Validator | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 3567.1740 |

## Sequential improvements

Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.

| From | To | Metric | Delta | Relative change | Improvement |
| --- | --- | --- | ---: | ---: | ---: |
| A | B | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| A | B | mrr | 0.0000 | 0.0000 | 0.0000 |
| A | B | answer_correctness | 0.0000 | 0.0000 | 0.0000 |
| A | B | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| A | B | citation_precision | 0.0000 | N/A | 0.0000 |
| A | B | hallucination | 0.0000 | N/A | -0.0000 |
| A | B | total_latency_ms | -1332.1010 | -50.3202 | 1332.1010 |
| A | B | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| A | B | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| A | B | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| A | B | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| A | B | citation_coverage | 0.0000 | N/A | 0.0000 |
| A | B | citation_recall | 0.0000 | N/A | 0.0000 |
| A | B | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| A | B | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| A | B | retrieval_latency_ms | -135.8710 | -26.9204 | 135.8710 |
| A | B | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| B | C | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| B | C | mrr | 0.0000 | 0.0000 | 0.0000 |
| B | C | answer_correctness | 0.0000 | 0.0000 | 0.0000 |
| B | C | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| B | C | citation_precision | 0.0000 | N/A | 0.0000 |
| B | C | hallucination | 0.0000 | N/A | -0.0000 |
| B | C | total_latency_ms | 37517.8390 | 2852.7422 | -37517.8390 |
| B | C | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| B | C | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| B | C | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| B | C | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| B | C | citation_coverage | 0.0000 | N/A | 0.0000 |
| B | C | citation_recall | 0.0000 | N/A | 0.0000 |
| B | C | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| B | C | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| B | C | retrieval_latency_ms | 37267.2180 | 10103.8434 | -37267.2180 |
| B | C | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| C | D | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | mrr | 0.0000 | 0.0000 | 0.0000 |
| C | D | answer_correctness | 0.0000 | 0.0000 | 0.0000 |
| C | D | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_precision | 1.0000 | N/A | 1.0000 |
| C | D | hallucination | 0.0000 | N/A | -0.0000 |
| C | D | total_latency_ms | -35265.8150 | -90.8141 | 35265.8150 |
| C | D | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| C | D | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_coverage | 1.0000 | N/A | 1.0000 |
| C | D | citation_recall | 1.0000 | N/A | 1.0000 |
| C | D | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| C | D | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| C | D | retrieval_latency_ms | -34967.4900 | -92.9095 | 34967.4900 |
| C | D | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
