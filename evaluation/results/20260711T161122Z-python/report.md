# Measured experiment results

These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dense RAG | 0.7355 | 0.6465 | 0.5081 | 0.8871 | 0.0000 | 0.1774 | 30.4944 |
| Hybrid RAG | 0.8498 | 0.7516 | 0.5201 | 0.9395 | 0.0000 | 0.1573 | 27.0037 |
| Hybrid + Reranker | 0.9139 | 0.7990 | 0.5449 | 0.9113 | 0.0000 | 0.1774 | 29.2071 |
| Hybrid + Validator | 0.9139 | 0.7990 | 0.4816 | 0.9073 | 0.9531 | 0.1815 | 45.8086 |

## Sequential improvements

Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.

| From | To | Metric | Delta | Relative change | Improvement |
| --- | --- | --- | ---: | ---: | ---: |
| A | B | recall_at_5 | 0.1142 | 15.5319 | 0.1142 |
| A | B | mrr | 0.1051 | 16.2550 | 0.1051 |
| A | B | answer_correctness | 0.0120 | 2.3563 | 0.0120 |
| A | B | faithfulness | 0.0524 | 5.9091 | 0.0524 |
| A | B | citation_precision | 0.0000 | N/A | 0.0000 |
| A | B | hallucination | -0.0202 | -11.3636 | 0.0202 |
| A | B | total_latency_ms | -3.4907 | -11.4471 | 3.4907 |
| A | B | recall_at_3 | 0.0986 | 13.9690 | 0.0986 |
| A | B | recall_at_10 | 0.0892 | 10.9827 | 0.0892 |
| A | B | precision_at_5 | 0.0244 | 15.7576 | 0.0244 |
| A | B | ndcg_at_10 | 0.1017 | 14.8862 | 0.1017 |
| A | B | citation_coverage | 0.0000 | N/A | 0.0000 |
| A | B | citation_recall | 0.0000 | N/A | 0.0000 |
| A | B | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| A | B | unsupported_claim_rate | -0.0524 | -46.4286 | 0.0524 |
| A | B | retrieval_latency_ms | -2.9502 | -11.4654 | 2.9502 |
| A | B | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| B | C | recall_at_5 | 0.0642 | 7.5506 | 0.0642 |
| B | C | mrr | 0.0474 | 6.3105 | 0.0474 |
| B | C | answer_correctness | 0.0249 | 4.7856 | 0.0249 |
| B | C | faithfulness | -0.0282 | -3.0043 | -0.0282 |
| B | C | citation_precision | 0.0000 | N/A | 0.0000 |
| B | C | hallucination | 0.0202 | 12.8205 | -0.0202 |
| B | C | total_latency_ms | 2.2034 | 8.1596 | -2.2034 |
| B | C | recall_at_3 | 0.0728 | 9.0467 | 0.0728 |
| B | C | recall_at_10 | 0.0352 | 3.9062 | 0.0352 |
| B | C | precision_at_5 | 0.0141 | 7.8534 | 0.0141 |
| B | C | ndcg_at_10 | 0.0466 | 5.9326 | 0.0466 |
| B | C | citation_coverage | 0.0000 | N/A | 0.0000 |
| B | C | citation_recall | 0.0000 | N/A | 0.0000 |
| B | C | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| B | C | unsupported_claim_rate | 0.0282 | 46.6667 | -0.0282 |
| B | C | retrieval_latency_ms | 0.6833 | 2.9995 | -0.6833 |
| B | C | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| C | D | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | mrr | 0.0000 | 0.0000 | 0.0000 |
| C | D | answer_correctness | -0.0633 | -11.6206 | -0.0633 |
| C | D | faithfulness | -0.0040 | -0.4425 | -0.0040 |
| C | D | citation_precision | 0.9531 | N/A | 0.9531 |
| C | D | hallucination | 0.0040 | 2.2727 | -0.0040 |
| C | D | total_latency_ms | 16.6015 | 56.8405 | -16.6015 |
| C | D | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| C | D | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_coverage | 0.7636 | N/A | 0.7636 |
| C | D | citation_recall | 0.8271 | N/A | 0.8271 |
| C | D | refusal_correct | 0.0000 | 0.0000 | 0.0000 |
| C | D | unsupported_claim_rate | 0.0040 | 4.5455 | -0.0040 |
| C | D | retrieval_latency_ms | -2.3678 | -10.0913 | 2.3678 |
| C | D | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
