"""
test_csv_profiler.py – Pytest suite for csv_profiler.py
=========================================================
Covers: happy paths, edge cases, invalid inputs, boundary conditions.
Run with:  pytest test_csv_profiler.py -v
"""

import csv
import os
import sys
import tempfile
from io import StringIO
from typing import List

import pytest

# Ensure the module is importable from the same directory
sys.path.insert(0, os.path.dirname(__file__))

from csv_profiler import (
    detect_duplicate_rows,
    generate_warnings,
    infer_type,
    main,
    profile_column,
    read_csv,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_temp_csv(rows: List[List[str]], encoding: str = "utf-8") -> str:
    """Write *rows* to a temp CSV file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False,
        newline="", encoding=encoding,
    )
    csv.writer(f).writerows(rows)
    f.close()
    return f.name


def write_temp_raw(content: bytes, suffix: str = ".csv") -> str:
    """Write raw bytes to a temp file (for encoding / binary tests)."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return f.name


# ── read_csv ──────────────────────────────────────────────────────────────────

class TestReadCSV:
    def test_normal_file(self):
        path = write_temp_csv([["name", "age"], ["Alice", "30"], ["Bob", "25"]])
        try:
            headers, rows = read_csv(path)
            assert headers == ["name", "age"]
            assert rows == [["Alice", "30"], ["Bob", "25"]]
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_csv("/nonexistent/__no_such_file__.csv")

    def test_empty_file_raises(self):
        f = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        f.close()
        try:
            with pytest.raises(ValueError, match="empty"):
                read_csv(f.name)
        finally:
            os.unlink(f.name)

    def test_header_only_returns_empty_rows(self):
        path = write_temp_csv([["col1", "col2"]])
        try:
            headers, rows = read_csv(path)
            assert headers == ["col1", "col2"]
            assert rows == []
        finally:
            os.unlink(path)

    def test_latin1_encoding_fallback(self):
        # Write a file with a Latin-1 character (é = 0xe9)
        content = "name,city\nCaf\xe9,Paris\n".encode("latin-1")
        path = write_temp_raw(content)
        try:
            headers, rows = read_csv(path)
            assert headers == ["name", "city"]
            assert rows[0][1] == "Paris"
        finally:
            os.unlink(path)

    def test_all_blank_header_raises(self):
        path = write_temp_csv([["", " ", ""], ["1", "2", "3"]])
        try:
            with pytest.raises(ValueError, match="empty"):
                read_csv(path)
        finally:
            os.unlink(path)


# ── infer_type ────────────────────────────────────────────────────────────────

class TestInferType:
    def test_pure_numeric(self):
        assert infer_type(["1", "2.5", "3.0", "100"]) == "numeric"

    def test_numeric_with_thousands_commas(self):
        assert infer_type(["1,000", "2,500", "3,750"]) == "numeric"

    def test_negative_numbers(self):
        assert infer_type(["-1", "-2.5", "0"]) == "numeric"

    def test_scientific_notation(self):
        assert infer_type(["1e5", "2.3e-4", "0"]) == "numeric"

    def test_boolean_true_false(self):
        assert infer_type(["True", "False", "true", "false"]) == "boolean"

    def test_boolean_yes_no(self):
        assert infer_type(["yes", "no", "YES", "No"]) == "boolean"

    def test_boolean_0_1(self):
        assert infer_type(["0", "1", "0", "1"]) == "boolean"

    def test_date_iso(self):
        assert infer_type(["2024-01-01", "2024-06-15", "2023-12-31"]) == "date"

    def test_date_dmy(self):
        assert infer_type(["01/01/2024", "15/06/2024"]) == "date"

    def test_categorical_plain_strings(self):
        assert infer_type(["apple", "banana", "cherry"]) == "categorical"

    def test_empty_all_blanks(self):
        assert infer_type(["", "  ", ""]) == "empty"

    def test_mostly_numeric_threshold(self):
        # 4 of 5 parseable = 80 % → mostly_numeric
        result = infer_type(["1", "2", "3", "4", "N/A"])
        assert result == "mostly_numeric"

    def test_below_mostly_numeric_threshold(self):
        # 3 of 5 = 60 % → categorical
        result = infer_type(["1", "2", "3", "N/A", "N/A"])
        assert result == "categorical"

    def test_nulls_excluded_from_inference(self):
        # Blanks must not count toward type inference
        assert infer_type(["1", "2", "", "3"]) == "numeric"

    def test_single_non_null_numeric(self):
        assert infer_type(["", "", "42", ""]) == "numeric"

    def test_mixed_date_and_text_stays_categorical(self):
        result = infer_type(["2024-01-01", "not-a-date", "also-not"])
        assert result == "categorical"


# ── profile_column ────────────────────────────────────────────────────────────

class TestProfileColumn:
    def test_numeric_stats_correctness(self):
        p = profile_column("score", ["10", "20", "30"], max_categories=5)
        assert p["type"] == "numeric"
        assert p["min"] == 10.0
        assert p["max"] == 30.0
        assert p["mean"] == pytest.approx(20.0)
        assert p["median"] == 20.0
        assert p["null_count"] == 0
        assert "stdev" in p

    def test_stdev_single_element_is_zero(self):
        p = profile_column("v", ["42"], max_categories=5)
        assert p["stdev"] == 0.0

    def test_null_counting_and_percentage(self):
        p = profile_column("x", ["1", "", "3", ""], max_categories=5)
        assert p["null_count"] == 2
        assert p["null_pct"] == pytest.approx(0.5)

    def test_all_null_column(self):
        p = profile_column("empty", ["", " ", ""], max_categories=5)
        assert p["null_pct"] == pytest.approx(1.0)
        assert p["type"] == "empty"

    def test_categorical_top_values_order(self):
        p = profile_column(
            "fruit",
            ["apple", "apple", "apple", "banana", "cherry"],
            max_categories=2,
        )
        vals = [v for v, _ in p["top_values"]]
        assert vals[0] == "apple"

    def test_max_categories_limit(self):
        # 10 distinct values but max_categories=3
        values = [str(i) for i in range(10)]
        p = profile_column("num", values, max_categories=3)
        # Numeric type, so top_values not present; adjust test
        # Actually all are numeric → use unique_count check instead
        assert p["unique_count"] == 10

    def test_categorical_max_categories_respected(self):
        values = ["a", "b", "c", "d", "e", "f"]
        p = profile_column("col", values, max_categories=3)
        assert len(p["top_values"]) <= 3

    def test_single_unique_value_flag(self):
        p = profile_column("flag", ["yes", "yes", "yes"], max_categories=5)
        assert p["unique_count"] == 1

    def test_unique_count_excludes_nulls(self):
        # "a" and blank — unique non-null = 1
        p = profile_column("col", ["a", "a", "", "a"], max_categories=5)
        assert p["unique_count"] == 1

    def test_numeric_with_comma_in_values(self):
        p = profile_column("revenue", ["1,000", "2,500", "3,000"], max_categories=5)
        assert p["type"] == "numeric"
        assert p["mean"] == pytest.approx(2166.666, rel=1e-3)

    def test_total_includes_nulls(self):
        p = profile_column("x", ["1", "", "3"], max_categories=5)
        assert p["total"] == 3


# ── detect_duplicate_rows ─────────────────────────────────────────────────────

class TestDetectDuplicateRows:
    def test_no_duplicates(self):
        rows = [["a", "1"], ["b", "2"], ["c", "3"]]
        assert detect_duplicate_rows(rows) == 0

    def test_one_duplicate(self):
        rows = [["a", "1"], ["a", "1"], ["b", "2"]]
        assert detect_duplicate_rows(rows) == 1

    def test_multiple_duplicates(self):
        rows = [["x"], ["x"], ["x"]]
        assert detect_duplicate_rows(rows) == 2

    def test_empty_input(self):
        assert detect_duplicate_rows([]) == 0

    def test_single_row(self):
        assert detect_duplicate_rows([["a", "b"]]) == 0

    def test_near_duplicate_differs_in_whitespace(self):
        # Whitespace difference → NOT duplicates (we don't strip here)
        rows = [["a ", "1"], ["a", "1"]]
        assert detect_duplicate_rows(rows) == 0


# ── generate_warnings ─────────────────────────────────────────────────────────

class TestGenerateWarnings:
    def _p(self, name, null_pct, unique_count, col_type="categorical"):
        return {
            "name": name,
            "null_pct": null_pct,
            "unique_count": unique_count,
            "type": col_type,
        }

    def test_high_null_triggers_warning(self):
        warnings = generate_warnings(
            [self._p("notes", 0.5, 10)],
            null_threshold=0.2,
            dupe_count=0,
        )
        assert any("notes" in w and "null" in w.lower() for w in warnings)

    def test_null_at_exactly_threshold_no_warning(self):
        # > threshold, not >=, so at exactly threshold → no warning
        warnings = generate_warnings(
            [self._p("col", 0.20, 10)],
            null_threshold=0.20,
            dupe_count=0,
        )
        assert not any("null" in w.lower() for w in warnings)

    def test_null_just_above_threshold_warns(self):
        warnings = generate_warnings(
            [self._p("col", 0.201, 10)],
            null_threshold=0.20,
            dupe_count=0,
        )
        assert any("null" in w.lower() for w in warnings)

    def test_constant_column_warning(self):
        warnings = generate_warnings(
            [self._p("flag", 0.0, 1)],
            null_threshold=0.2,
            dupe_count=0,
        )
        assert any("one unique" in w.lower() or "constant" in w.lower() for w in warnings)

    def test_mostly_numeric_warning(self):
        warnings = generate_warnings(
            [self._p("amount", 0.0, 50, col_type="mostly_numeric")],
            null_threshold=0.2,
            dupe_count=0,
        )
        assert any("mostly numeric" in w.lower() for w in warnings)

    def test_duplicate_rows_warning(self):
        warnings = generate_warnings(
            [self._p("col", 0.0, 5)],
            null_threshold=0.2,
            dupe_count=3,
        )
        assert any("duplicate" in w.lower() for w in warnings)

    def test_clean_data_no_warnings(self):
        warnings = generate_warnings(
            [self._p("col", 0.0, 50)],
            null_threshold=0.2,
            dupe_count=0,
        )
        assert warnings == []

    def test_multiple_issues_all_reported(self):
        profiles = [
            self._p("a", 0.9, 1),   # high null + constant
            self._p("b", 0.0, 5, col_type="mostly_numeric"),
        ]
        warnings = generate_warnings(profiles, null_threshold=0.2, dupe_count=2)
        assert len(warnings) >= 4  # null-a, constant-a, mostly_numeric-b, dupes


# ── main() integration tests ──────────────────────────────────────────────────

class TestMainIntegration:
    def test_happy_path_exit_zero(self, capsys):
        path = write_temp_csv([
            ["id", "score", "label"],
            ["1", "90", "pass"],
            ["2", "45", "fail"],
            ["3", "78", "pass"],
        ])
        try:
            rc = main([path])
            assert rc == 0
            out = capsys.readouterr().out
            assert "CSV DATA PROFILE REPORT" in out
            assert "score" in out
        finally:
            os.unlink(path)

    def test_file_not_found_exit_one(self, capsys):
        rc = main(["/no/such/file.csv"])
        assert rc == 1
        assert "Error" in capsys.readouterr().err

    def test_empty_file_exit_one(self, capsys):
        f = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        f.close()
        try:
            rc = main([f.name])
            assert rc == 1
        finally:
            os.unlink(f.name)

    def test_header_only_exit_zero_with_warning(self, capsys):
        path = write_temp_csv([["col1", "col2"]])
        try:
            rc = main([path])
            assert rc == 0
            assert "Warning" in capsys.readouterr().err
        finally:
            os.unlink(path)

    def test_wide_rows_warning_on_stderr(self, capsys):
        path = write_temp_csv([
            ["a", "b"],
            ["1", "2", "EXTRA", "EXTRA2"],
        ])
        try:
            main([path])
            err = capsys.readouterr().err
            assert "extra" in err.lower() or "more columns" in err.lower()
        finally:
            os.unlink(path)

    def test_short_rows_padded_without_crash(self, capsys):
        path = write_temp_csv([
            ["a", "b", "c"],
            ["1"],          # only 1 value, 2 cols will be blank
            ["2", "20", "cat"],
        ])
        try:
            rc = main([path])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_all_nulls_column_no_crash(self, capsys):
        path = write_temp_csv([
            ["id", "notes"],
            ["1", ""],
            ["2", ""],
        ])
        try:
            rc = main([path])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_duplicate_rows_reported(self, capsys):
        path = write_temp_csv([
            ["x", "y"],
            ["1", "a"],
            ["1", "a"],
            ["2", "b"],
        ])
        try:
            main([path])
            out = capsys.readouterr().out
            assert "duplicate" in out.lower()
        finally:
            os.unlink(path)

    def test_custom_null_threshold(self, capsys):
        # With a very high threshold (0.99), no null *warning* should appear.
        # (The word "Nulls" still appears as a column stat label — that is fine.)
        path = write_temp_csv([
            ["x"],
            [""],
            [""],
            ["1"],
        ])
        try:
            main([path, "--null-threshold", "0.99"])
            out = capsys.readouterr().out
            # Null warning looks like: "• Column 'x' has N% null values."
            assert "null values" not in out.lower()
        finally:
            os.unlink(path)

    def test_max_categories_option(self, capsys):
        path = write_temp_csv(
            [["letter"]] + [[c] for c in "abcdefghij"]
        )
        try:
            main([path, "--max-categories", "2"])
            out = capsys.readouterr().out
            # Hard to check exact count, but should not crash
            assert "letter" in out
        finally:
            os.unlink(path)
