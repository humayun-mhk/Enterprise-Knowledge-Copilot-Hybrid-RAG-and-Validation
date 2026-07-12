from evaluation.io_utils import load_benchmark
from scripts.validate_evaluation_assets import ROOT, validate


def test_generated_assets_are_complete() -> None:
    summary = validate()
    assert summary["documents"] == 12
    assert summary["benchmark_questions"] >= 240
    assert summary["logical_pages"] == 48


def test_jsonl_and_csv_load_to_same_ids() -> None:
    json_items = load_benchmark(ROOT / "data" / "benchmark" / "enterprise_qa_v1.jsonl")
    csv_items = load_benchmark(ROOT / "data" / "benchmark" / "enterprise_qa_v1.csv")
    assert [item.item_id for item in json_items] == [item.item_id for item in csv_items]
    assert [item.relevant_targets for item in json_items] == [item.relevant_targets for item in csv_items]
    assert [item.source_passages for item in json_items] == [item.source_passages for item in csv_items]
    assert any(len(item.relevant_targets) > 1 for item in json_items)
