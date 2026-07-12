# Measured experiment results

These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dense RAG | 1.0000 | 0.9725 | 0.8103 | 0.8622 | 0.0000 | 0.1400 | 1194.7301 |
| Hybrid RAG | 1.0000 | 0.9458 | 0.7912 | 0.8807 | 0.0000 | 0.1200 | 1207.4839 |
| Hybrid + Reranker | 1.0000 | 0.9725 | 0.8139 | 0.8729 | 0.0000 | 0.1400 | 2025.3248 |
| Hybrid + Validator | 0.9900 | 0.9625 | 0.6953 | 0.9451 | 0.7980 | 0.0505 | 4883.1959 |

## Sequential improvements

Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.

| From | To | Metric | Delta | Relative change | Improvement |
| --- | --- | --- | ---: | ---: | ---: |
| A | B | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| A | B | mrr | -0.0267 | -2.7421 | -0.0267 |
| A | B | answer_correctness | -0.0191 | -2.3600 | -0.0191 |
| A | B | faithfulness | 0.0185 | 2.1406 | 0.0185 |
| A | B | citation_precision | 0.0000 | N/A | 0.0000 |
| A | B | hallucination | -0.0200 | -14.2857 | 0.0200 |
| A | B | total_latency_ms | 12.7538 | 1.0675 | -12.7538 |
| A | B | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| A | B | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| A | B | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| A | B | ndcg_at_10 | -0.0198 | -2.0176 | -0.0198 |
| A | B | citation_coverage | 0.0000 | N/A | 0.0000 |
| A | B | citation_recall | 0.0000 | N/A | 0.0000 |
| A | B | refusal_correct | -0.0300 | -3.0612 | -0.0300 |
| A | B | unsupported_claim_rate | -0.0185 | -13.3983 | 0.0185 |
| A | B | retrieval_latency_ms | 24.7035 | 5.2277 | -24.7035 |
| A | B | estimated_cost_usd | -0.0000 | -0.1946 | 0.0000 |
| B | C | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| B | C | mrr | 0.0267 | 2.8194 | 0.0267 |
| B | C | answer_correctness | 0.0228 | 2.8759 | 0.0228 |
| B | C | faithfulness | -0.0078 | -0.8913 | -0.0078 |
| B | C | citation_precision | 0.0000 | N/A | 0.0000 |
| B | C | hallucination | 0.0200 | 16.6667 | -0.0200 |
| B | C | total_latency_ms | 817.8408 | 67.7310 | -817.8408 |
| B | C | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| B | C | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| B | C | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| B | C | ndcg_at_10 | 0.0198 | 2.0591 | 0.0198 |
| B | C | citation_coverage | 0.0000 | N/A | 0.0000 |
| B | C | citation_recall | 0.0000 | N/A | 0.0000 |
| B | C | refusal_correct | 0.0200 | 2.1053 | 0.0200 |
| B | C | unsupported_claim_rate | 0.0078 | 6.5797 | -0.0078 |
| B | C | retrieval_latency_ms | 827.4181 | 166.3989 | -827.4181 |
| B | C | estimated_cost_usd | 0.0000 | 0.1625 | -0.0000 |
| C | D | recall_at_5 | -0.0100 | -1.0000 | -0.0100 |
| C | D | mrr | -0.0100 | -1.0283 | -0.0100 |
| C | D | answer_correctness | -0.1187 | -14.5795 | -0.1187 |
| C | D | faithfulness | 0.0723 | 8.2827 | 0.0723 |
| C | D | citation_precision | 0.7980 | N/A | 0.7980 |
| C | D | hallucination | -0.0895 | -63.9250 | 0.0895 |
| C | D | total_latency_ms | 2857.8712 | 141.1068 | -2857.8712 |
| C | D | recall_at_3 | -0.0100 | -1.0101 | -0.0100 |
| C | D | recall_at_10 | -0.0100 | -1.0000 | -0.0100 |
| C | D | precision_at_5 | -0.0020 | -1.0000 | -0.0020 |
| C | D | ndcg_at_10 | -0.0100 | -1.0209 | -0.0100 |
| C | D | citation_coverage | 0.9557 | N/A | 0.9557 |
| C | D | citation_recall | 0.7800 | N/A | 0.7800 |
| C | D | refusal_correct | -0.1700 | -17.5258 | -0.1700 |
| C | D | unsupported_claim_rate | -0.0723 | -56.8594 | 0.0723 |
| C | D | retrieval_latency_ms | -280.2762 | -21.1582 | 280.2762 |
| C | D | estimated_cost_usd | -0.0002 | -2.2302 | 0.0002 |
