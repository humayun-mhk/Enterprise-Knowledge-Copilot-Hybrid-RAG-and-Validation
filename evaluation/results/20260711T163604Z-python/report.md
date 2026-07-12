# Measured experiment results

These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dense RAG | 0.7355 | 0.6465 | 0.5847 | 1.0000 | 0.0000 | 0.0645 | 24.8760 |
| Hybrid RAG | 0.8498 | 0.7508 | 0.5645 | 1.0000 | 0.0000 | 0.0968 | 34.7298 |
| Hybrid + Reranker | 0.9139 | 0.7994 | 0.5974 | 1.0000 | 0.0000 | 0.0887 | 27.9056 |
| Hybrid + Validator | 0.9139 | 0.7994 | 0.5342 | 1.0000 | 0.9531 | 0.0887 | 47.2310 |

## Sequential improvements

Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.

| From | To | Metric | Delta | Relative change | Improvement |
| --- | --- | --- | ---: | ---: | ---: |
| A | B | recall_at_5 | 0.1142 | 15.5319 | 0.1142 |
| A | B | mrr | 0.1043 | 16.1340 | 0.1043 |
| A | B | answer_correctness | -0.0202 | -3.4571 | -0.0202 |
| A | B | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| A | B | citation_precision | 0.0000 | N/A | 0.0000 |
| A | B | hallucination | 0.0323 | 50.0000 | -0.0323 |
| A | B | total_latency_ms | 9.8538 | 39.6115 | -9.8538 |
| A | B | recall_at_3 | 0.0986 | 13.9690 | 0.0986 |
| A | B | recall_at_10 | 0.0892 | 10.9827 | 0.0892 |
| A | B | precision_at_5 | 0.0244 | 15.7576 | 0.0244 |
| A | B | ndcg_at_10 | 0.1012 | 14.8125 | 0.1012 |
| A | B | citation_coverage | 0.0000 | N/A | 0.0000 |
| A | B | citation_recall | 0.0000 | N/A | 0.0000 |
| A | B | refusal_correct | -0.0121 | -1.3453 | -0.0121 |
| A | B | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| A | B | retrieval_latency_ms | 8.7378 | 41.3795 | -8.7378 |
| A | B | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| B | C | recall_at_5 | 0.0642 | 7.5506 | 0.0642 |
| B | C | mrr | 0.0486 | 6.4734 | 0.0486 |
| B | C | answer_correctness | 0.0329 | 5.8343 | 0.0329 |
| B | C | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| B | C | citation_precision | 0.0000 | N/A | 0.0000 |
| B | C | hallucination | -0.0081 | -8.3333 | 0.0081 |
| B | C | total_latency_ms | -6.8242 | -19.6494 | 6.8242 |
| B | C | recall_at_3 | 0.0775 | 9.6304 | 0.0775 |
| B | C | recall_at_10 | 0.0352 | 3.9062 | 0.0352 |
| B | C | precision_at_5 | 0.0141 | 7.8534 | 0.0141 |
| B | C | ndcg_at_10 | 0.0474 | 6.0420 | 0.0474 |
| B | C | citation_coverage | 0.0000 | N/A | 0.0000 |
| B | C | citation_recall | 0.0000 | N/A | 0.0000 |
| B | C | refusal_correct | -0.0121 | -1.3636 | -0.0121 |
| B | C | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| B | C | retrieval_latency_ms | -7.8633 | -26.3390 | 7.8633 |
| B | C | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| C | D | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | mrr | 0.0000 | 0.0000 | 0.0000 |
| C | D | answer_correctness | -0.0632 | -10.5830 | -0.0632 |
| C | D | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_precision | 0.9531 | N/A | 0.9531 |
| C | D | hallucination | 0.0000 | 0.0000 | -0.0000 |
| C | D | total_latency_ms | 19.3255 | 69.2530 | -19.3255 |
| C | D | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| C | D | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_coverage | 0.8020 | N/A | 0.8020 |
| C | D | citation_recall | 0.8271 | N/A | 0.8271 |
| C | D | refusal_correct | -0.0040 | -0.4608 | -0.0040 |
| C | D | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| C | D | retrieval_latency_ms | -1.3973 | -6.3539 | 1.3973 |
| C | D | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
