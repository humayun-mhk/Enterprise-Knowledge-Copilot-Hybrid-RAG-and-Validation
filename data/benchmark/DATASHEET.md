# Enterprise QA v1 datasheet

Purpose: compare retrieval and grounded-answer behavior across controlled RAG ablations. The set is synthetic and may be used in CI, demos, and local experiments without exposing enterprise data.

The 248 records include exact policy questions, ordinary answerable questions, paraphrases, multi-document questions, deliberately ambiguous questions, questions not covered by the corpus, and prompt-injection/counterfactual adversarial questions. Each record contains the required question, expected answer, expected document, expected logical page, answerability label, and expected keywords. Additional fields provide a stable ID, category, fact IDs, and the source passage.

The benchmark is generated from the same fact catalog as the source documents to prevent accidental page drift. This makes it suitable for deterministic retrieval checks, but it should not be treated as a substitute for a separately authored human test set. Before production rollout, add a private holdout set written by subject-matter experts and sample outputs for blinded human review.

No scores are embedded in the dataset. All reported metrics must originate from captured pipeline outputs.
