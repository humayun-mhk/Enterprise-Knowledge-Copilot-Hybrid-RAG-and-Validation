from __future__ import annotations

import csv

from evaluation.reporting import write_human_review_sample


def test_human_review_sample_is_stratified_by_experiment_and_category(tmp_path) -> None:
    experiments = ("A", "B", "C", "D")
    categories = ("exact_policy", "multi_document", "unanswerable")
    rows = [
        {
            "experiment_id": experiment,
            "item_id": f"{experiment}-{category}",
            "category": category,
            "question": "q",
            "expected_answer": "e",
            "answer": "a",
            "answer_correctness": 0.5,
            "unsupported_claim_rate": 0.0,
        }
        for experiment in experiments
        for category in categories
    ]
    path = tmp_path / "review.csv"

    write_human_review_sample(rows, path, limit=len(rows))

    with path.open(encoding="utf-8-sig", newline="") as handle:
        sampled = list(csv.DictReader(handle))
    assert {(row["experiment_id"], row["category"]) for row in sampled} == {
        (experiment, category)
        for experiment in experiments
        for category in categories
    }

