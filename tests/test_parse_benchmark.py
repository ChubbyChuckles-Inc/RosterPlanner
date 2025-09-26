import json
from gui.ingestion.parse_benchmark import run_benchmark, BenchmarkVariant


def tiny_rules_a():
    return {
        "version": 1,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points"],
            }
        },
    }


def tiny_rules_b():
    # Add an extra column (simulating slightly different extraction)
    return {
        "version": 1,
        "resources": {
            "ranking_table": {
                "kind": "table",
                "selector": "table.ranking",
                "columns": ["team", "points", "diff"],
            }
        },
    }


def sample_html():
    # Very small HTML with a simplistic table; parsing logic in generate_parse_preview
    # will decide how many rows; here we assume selector picks something; we just need structural test.
    return {
        "file1.html": "<table class='ranking'><tr><td>A</td><td>10</td><td>1</td></tr>"
        "<tr><td>B</td><td>8</td><td>2</td></tr></table>",
        "file2.html": "<table class='ranking'><tr><td>C</td><td>7</td><td>3</td></tr></table>",
    }


def test_run_benchmark_basic_diff():
    variants = [
        BenchmarkVariant("A", json.dumps(tiny_rules_a())),
        BenchmarkVariant("B", json.dumps(tiny_rules_b())),
    ]
    results = run_benchmark(variants, sample_html())
    assert len(results) == 2
    a, b = results
    assert a.variant == "A" and b.variant == "B"
    # Ensure timing recorded (non-negative)
    assert a.total_ms >= 0 and b.total_ms >= 0
    # diff_vs_base exists for B
    assert b.diff_vs_base is not None
    # At least the ranking_table key present
    assert "ranking_table" in b.diff_vs_base


def test_run_benchmark_handles_bad_json():
    variants = [
        BenchmarkVariant("A", "{"),  # malformed JSON
        BenchmarkVariant("B", json.dumps(tiny_rules_a())),
    ]
    results = run_benchmark(variants, sample_html())
    assert len(results) == 2
    assert results[0].error is not None
    assert results[1].error is None
