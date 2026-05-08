from pathlib import Path

from llm_ontology.data.format import load_domain_records, write_jsonl
from llm_ontology.data.marv import build_instruction_records, stratified_split
from llm_ontology.data.methods2test import prepare_methods2test
from llm_ontology.data.split import combine_records, split_records
from llm_ontology.finetuning.dataset_loader import load_jsonl


def test_format_refactoring_jsonl(tmp_path: Path) -> None:
    raw = tmp_path / "raw.jsonl"
    raw.write_text('{"before": "int a(){return 1;}", "after": "int answer(){return 1;}"}\n', encoding="utf-8")

    records = load_domain_records([raw], "refactoring")

    assert records == [
        {
            "instruction": "Refaktoruj nasledujúcu Java metódu.",
            "input": "int a(){return 1;}",
            "output": "int answer(){return 1;}",
            "domain": "refactoring",
        }
    ]


def test_write_and_load_instruction_dataset(tmp_path: Path) -> None:
    output = tmp_path / "train.jsonl"
    records = [{"instruction": "i", "input": "x", "output": "y", "domain": "testing"}]

    write_jsonl(records, output)

    assert load_jsonl(output) == records


def test_split_and_combine_records() -> None:
    records = [{"id": index} for index in range(10)]
    train, val, test = split_records(records, seed=1)

    assert len(train) == 8
    assert len(val) == 1
    assert len(test) == 1
    assert len(combine_records(train, val, test)) == 10


def test_prepare_methods2test_uses_official_splits(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus" / "json"
    good_input = "public int add(int a, int b) { int result = a + b; return result; }"
    good_output = "@Test public void testAdd() { assertEquals(3, add(1, 2)); }"
    bad_output = "public void helper() {}"
    for split in ("train", "eval", "test"):
        split_dir = corpus / split / "123"
        split_dir.mkdir(parents=True)
        (split_dir / "123_0_corpus.json").write_text(
            f'{{"src_fm": "{good_input}", "target": "{good_output}"}}',
            encoding="utf-8",
        )
        (split_dir / "123_1_corpus.json").write_text(
            f'{{"src_fm": "{good_input}", "target": "{bad_output}"}}',
            encoding="utf-8",
        )

    stats = prepare_methods2test(corpus, tmp_path / "processed", "src_fm", {"train": 1, "eval": 1, "test": 1})

    assert [item.saved for item in stats] == [1, 1, 1]
    assert (tmp_path / "processed" / "train.jsonl").exists()
    assert (tmp_path / "processed" / "val.jsonl").exists()
    assert (tmp_path / "processed" / "test.jsonl").exists()
    record = load_jsonl(tmp_path / "processed" / "val.jsonl")[0]
    assert record["source"] == "methods2test"
    assert record["context_level"] == "src_fm"
    assert record["source_file"].endswith("corpus/json/eval/123/123_0_corpus.json")


def test_marv_instruction_records_and_stratified_split() -> None:
    base = {
        "refactoring_id": "1",
        "commit_sha": "abc",
        "commit_link": "https://example.test/commit/abc",
        "file_path": "A.java",
        "description": "Rename method",
        "code_before": "public void oldName() { System.out.println(\"hello\"); }",
        "code_after": "public void newName() { System.out.println(\"hello\"); }",
        "evaluations": [{"vote": 1}, {"vote": -1}],
    }
    data = {
        "Extract Method": [dict(base, refactoring_id=f"e{index}") for index in range(10)],
        "Rename Method": [dict(base, refactoring_id=f"m{index}") for index in range(10)],
        "Rename Variable": [dict(base, refactoring_id=f"v{index}") for index in range(10)],
        "Remove Parameter": [dict(base, refactoring_id=f"p{index}") for index in range(10)],
    }

    loaded, skipped, records = build_instruction_records(data)
    splits = stratified_split(records)

    assert loaded == 40
    assert skipped == 0
    assert records[0]["domain"] == "refactoring"
    assert records[0]["source"] == "marv"
    assert records[0]["evaluation_votes"] == [1, -1]
    for split_records in splits.values():
        assert {record["refactoring_type"] for record in split_records} == set(data)
