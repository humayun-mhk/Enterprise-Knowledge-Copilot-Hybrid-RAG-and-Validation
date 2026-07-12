# Evaluation methodology

The evaluator compares four configurations while holding the corpus, benchmark, chunking settings, and query order constant. It writes raw per-question observations before aggregates so every reported number is auditable.

## Dataset composition

The generated benchmark contains answerable, multi-document, ambiguous, unanswerable, exact-detail, adversarial, and paraphrased questions. Each row includes:

- `question`
- `expected_answer`
- `expected_document`
- `expected_page`
- `answerable`
- `expected_keywords`
- a category and stable identifier for stratified reporting

Synthetic documents are marked as such. They are useful for reproducible engineering comparisons but do not claim to represent a real company's policies.

## Retrieval metrics

- **Recall@3/5/10**: fraction of questions whose expected evidence occurs in the top K.
- **Precision@K**: fraction of top-K passages that match the expected evidence set.
- **MRR**: reciprocal rank of the first expected passage, averaged over eligible questions.
- **nDCG@K**: discounted gain using document/page relevance labels.
- **Retrieval latency**: measured with a monotonic clock and reported with average and percentile summaries.

Unanswerable questions are excluded from evidence-recall denominators and evaluated through refusal metrics instead. A multi-document item is considered completely recalled only when all expected documents are present; partial-document recall is also retained in raw observations.

## Generation and safety metrics

Deterministic scoring covers expected keyword/answer matching, document/page citation correctness, citation coverage, citation precision/recall, unsupported sentence rate, and refusal accuracy. Optional semantic and LLM judges supplement these checks; they never replace ground-truth retrieval checks.

| Metric | Primary implementation |
|---|---|
| Answer correctness | normalized expected-answer and keyword match; optional semantic judge |
| Faithfulness | claim-to-evidence support plus optional judge |
| Relevance | deterministic term/semantic overlap plus optional judge |
| Contextual precision/recall | expected document/page labels |
| Hallucination rate | answerable output containing unsupported material claims |
| Refusal accuracy | confusion matrix against `answerable` |
| Citation precision/recall | cited chunk provenance against expected evidence |
| Unsupported claim rate | unsupported factual claims / total factual claims |
| Latency, tokens, cost | captured from runtime/provider usage metadata |

Cost is computed only when a versioned pricing configuration and actual token counts are available. Otherwise it remains `null`; the evaluator does not treat zero as “free.”

## Preventing invented results

The repository does not ship hand-entered benchmark scores. A report is valid only when it contains a run identifier, UTC timestamp, dataset fingerprint, corpus fingerprint, retrieval configuration hash, row count, and raw-observation artifact. Failed or unavailable model-dependent metrics are represented as `null` with a reason.

The comparison table and improvement columns are derived from the current aggregate JSON. Improvements use absolute percentage-point differences for bounded rates and relative percentage differences for latency/cost where a valid baseline exists.

## Human review

The evaluator produces a deterministic, stratified review sample. Reviewers score correctness, evidence support, relevance, citation correctness, and refusal behavior, and can add notes. Human labels should be imported as a separate artifact; they are never silently merged with automated judgments.

## Deployment gate

Pull-request CI validates corpus/benchmark contracts and runs backend, evaluator, and frontend tests. The manually triggered release workflow runs all 248 questions across A–D through the disclosed offline adapter before image construction. The live HTTP configuration is available for a deployed-stack benchmark. Teams should set quality thresholds only after recording an accepted baseline on their own corpus and infrastructure; the reference gate initially enforces zero evaluation errors.
