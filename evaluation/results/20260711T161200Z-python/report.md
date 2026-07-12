# Measured experiment results

These values were computed from captured pipeline outputs. `N/A` is preserved when an adapter did not expose the required field.

| System | Recall@5 | MRR | Correctness | Faithfulness | Citation Precision | Hallucination Rate | Latency (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dense RAG | 0.7355 | 0.6465 | 0.5847 | 1.0000 | 0.0000 | 0.0645 | 25.5113 |
| Hybrid RAG | 0.8498 | 0.7516 | 0.5644 | 1.0000 | 0.0000 | 0.0968 | 25.9377 |
| Hybrid + Reranker | 0.9139 | 0.7990 | 0.5974 | 1.0000 | 0.0000 | 0.0887 | 28.1495 |
| Hybrid + Validator | 0.9139 | 0.7990 | 0.5340 | 1.0000 | 0.9531 | 0.0887 | 47.0279 |

## Sequential improvements

Positive `improvement` means better after applying the metric's direction; raw `delta` is always candidate minus baseline.

| From | To | Metric | Delta | Relative change | Improvement |
| --- | --- | --- | ---: | ---: | ---: |
| A | B | recall_at_5 | 0.1142 | 15.5319 | 0.1142 |
| A | B | mrr | 0.1051 | 16.2550 | 0.1051 |
| A | B | answer_correctness | -0.0203 | -3.4695 | -0.0203 |
| A | B | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| A | B | citation_precision | 0.0000 | N/A | 0.0000 |
| A | B | hallucination | 0.0323 | 50.0000 | -0.0323 |
| A | B | total_latency_ms | 0.4264 | 1.6716 | -0.4264 |
| A | B | recall_at_3 | 0.0986 | 13.9690 | 0.0986 |
| A | B | recall_at_10 | 0.0892 | 10.9827 | 0.0892 |
| A | B | precision_at_5 | 0.0244 | 15.7576 | 0.0244 |
| A | B | ndcg_at_10 | 0.1017 | 14.8862 | 0.1017 |
| A | B | citation_coverage | 0.0000 | N/A | 0.0000 |
| A | B | citation_recall | 0.0000 | N/A | 0.0000 |
| A | B | refusal_correct | -0.0121 | -1.3453 | -0.0121 |
| A | B | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| A | B | retrieval_latency_ms | 0.1581 | 0.7227 | -0.1581 |
| A | B | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| B | C | recall_at_5 | 0.0642 | 7.5506 | 0.0642 |
| B | C | mrr | 0.0474 | 6.3105 | 0.0474 |
| B | C | answer_correctness | 0.0330 | 5.8383 | 0.0330 |
| B | C | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| B | C | citation_precision | 0.0000 | N/A | 0.0000 |
| B | C | hallucination | -0.0081 | -8.3333 | 0.0081 |
| B | C | total_latency_ms | 2.2118 | 8.5274 | -2.2118 |
| B | C | recall_at_3 | 0.0728 | 9.0467 | 0.0728 |
| B | C | recall_at_10 | 0.0352 | 3.9062 | 0.0352 |
| B | C | precision_at_5 | 0.0141 | 7.8534 | 0.0141 |
| B | C | ndcg_at_10 | 0.0466 | 5.9326 | 0.0466 |
| B | C | citation_coverage | 0.0000 | N/A | 0.0000 |
| B | C | citation_recall | 0.0000 | N/A | 0.0000 |
| B | C | refusal_correct | -0.0121 | -1.3636 | -0.0121 |
| B | C | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| B | C | retrieval_latency_ms | 0.7616 | 3.4568 | -0.7616 |
| B | C | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
| C | D | recall_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | mrr | 0.0000 | 0.0000 | 0.0000 |
| C | D | answer_correctness | -0.0633 | -10.6009 | -0.0633 |
| C | D | faithfulness | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_precision | 0.9531 | N/A | 0.9531 |
| C | D | hallucination | 0.0000 | 0.0000 | -0.0000 |
| C | D | total_latency_ms | 18.8784 | 67.0647 | -18.8784 |
| C | D | recall_at_3 | 0.0000 | 0.0000 | 0.0000 |
| C | D | recall_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | precision_at_5 | 0.0000 | 0.0000 | 0.0000 |
| C | D | ndcg_at_10 | 0.0000 | 0.0000 | 0.0000 |
| C | D | citation_coverage | 0.8012 | N/A | 0.8012 |
| C | D | citation_recall | 0.8271 | N/A | 0.8271 |
| C | D | refusal_correct | -0.0040 | -0.4608 | -0.0040 |
| C | D | unsupported_claim_rate | 0.0000 | N/A | -0.0000 |
| C | D | retrieval_latency_ms | -0.4116 | -1.8056 | 0.4116 |
| C | D | estimated_cost_usd | 0.0000 | N/A | -0.0000 |
