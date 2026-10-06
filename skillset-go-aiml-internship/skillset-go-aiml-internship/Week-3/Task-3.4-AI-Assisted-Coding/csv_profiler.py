"""
csv_profiler.py – CSV Data Profiler
====================================
Reads a CSV file and prints a concise per-column profile:
inferred type, null rate, stats (numeric) or top values (categorical),
plus dataset-level warnings.

No third-party dependencies – stdlib only.
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="csv_profiler",
        description="Profile a CSV file: types, nulls, stats, and warnings.",
    )
    parser.add_argument("filepath", help="Path to the CSV file to profile.")
    parser.add_argument(
        "--max-categories",
        type=int,
        default=5,
        metavar="N",
        help="Max top-values shown for categorical columns (default: 5).",
    )
    parser.add_argument(
        "--null-threshold",
        type=float,
        default=0.20,
        metavar="F",
        help="Null ratio that triggers a warning, 0–1 (default: 0.20).",
    )
    return parser.parse_args(argv)


# ── I/O ───────────────────────────────────────────────────────────────────────

def read_csv(filepath: str) -> Tuple[List[str], List[List[str]]]:
    """
    Read a CSV file and return (headers, data_rows).

    Raises:
        FileNotFoundError – path does not exist.
        ValueError        – file is empty, has no valid header, or cannot be decoded.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ValueError("File is empty (0 bytes).")

    for encoding in ("utf-8", "latin-1"):
        try:
            with open(filepath, newline="", encoding=encoding) as fh:
                reader = csv.reader(fh)
                try:
                    headers = next(reader)
                except StopIteration:
                    raise ValueError("CSV file contains no rows.")

                if not headers or all(h.strip() == "" for h in headers):
                    raise ValueError("CSV header row is empty or blank.")

                rows = list(reader)
            return headers, rows
        except UnicodeDecodeError:
            continue  # try next encoding

    raise ValueError(
        "Could not decode the file with UTF-8 or Latin-1. "
        "Please re-save it with UTF-8 encoding."
    )


# ── Type inference ────────────────────────────────────────────────────────────

_BOOL_TOKENS = {"true", "false", "yes", "no", "0", "1", "t", "f", "y", "n"}
_DATE_PATTERN = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}$"      # ISO: 2024-06-15
    r"|^\d{2}[-/]\d{2}[-/]\d{4}$"     # DMY: 15/06/2024
)


def _try_float(value: str) -> Optional[float]:
    """Return float if parseable (strips thousands commas), else None."""
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def infer_type(values: List[str]) -> str:
    """
    Infer the dominant type of a column from its raw string values.
    Null/blank values are excluded from inference.

    Returns one of: 'boolean', 'numeric', 'mostly_numeric', 'date',
                    'categorical', 'empty'.
    """
    non_null = [v.strip() for v in values if v.strip() != ""]
    if not non_null:
        return "empty"

    total = len(non_null)

    # Boolean check
    if all(v.lower() in _BOOL_TOKENS for v in non_null):
        return "boolean"

    # Numeric / mostly-numeric check
    numeric_count = sum(1 for v in non_null if _try_float(v) is not None)
    ratio = numeric_count / total
    if ratio == 1.0:
        return "numeric"
    if ratio >= 0.80:
        return "mostly_numeric"

    # Date check
    date_count = sum(1 for v in non_null if _DATE_PATTERN.match(v))
    if date_count / total >= 0.80:
        return "date"

    return "categorical"


# ── Column profiling ──────────────────────────────────────────────────────────

def profile_column(
    name: str,
    values: List[str],
    max_categories: int,
) -> Dict[str, Any]:
    """
    Compute a statistics dictionary for one CSV column.

    Keys always present:
        name, type, total, null_count, null_pct, unique_count

    Additional keys for 'numeric':
        min, max, mean, median, stdev

    Additional keys for all other types:
        top_values  (list of (value, count) tuples)
    """
    total = len(values)
    null_count = sum(1 for v in values if v.strip() == "")
    non_null = [v.strip() for v in values if v.strip() != ""]
    col_type = infer_type(values)

    profile: Dict[str, Any] = {
        "name": name,
        "type": col_type,
        "total": total,
        "null_count": null_count,
        "null_pct": null_count / total if total > 0 else 0.0,
        "unique_count": len(set(non_null)),
    }

    if col_type == "numeric" and non_null:
        nums = [_try_float(v) for v in non_null]  # all succeed by definition
        nums = [n for n in nums if n is not None]   # satisfy type checker
        profile["min"] = min(nums)
        profile["max"] = max(nums)
        profile["mean"] = mean(nums)
        profile["median"] = median(nums)
        profile["stdev"] = stdev(nums) if len(nums) > 1 else 0.0

    else:
        counter = Counter(non_null)
        profile["top_values"] = counter.most_common(max_categories)

    return profile


# ── Duplicate detection ───────────────────────────────────────────────────────

def detect_duplicate_rows(rows: List[List[str]]) -> int:
    """Return the number of rows that are exact duplicates of an earlier row."""
    seen: set = set()
    dupes = 0
    for row in rows:
        key = tuple(row)
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
    return dupes


# ── Warning generation ────────────────────────────────────────────────────────

def generate_warnings(
    profiles: List[Dict[str, Any]],
    null_threshold: float,
    dupe_count: int,
) -> List[str]:
    """Collect human-readable dataset-level warnings."""
    warnings: List[str] = []

    for p in profiles:
        if p["null_pct"] > null_threshold:
            warnings.append(
                f"Column '{p['name']}' has {p['null_pct']:.0%} null values."
            )
        if p["unique_count"] == 1:
            warnings.append(
                f"Column '{p['name']}' has only one unique value (constant column)."
            )
        if p["type"] == "mostly_numeric":
            warnings.append(
                f"Column '{p['name']}' is mostly numeric but contains some non-numeric values."
            )

    if dupe_count > 0:
        warnings.append(f"{dupe_count} duplicate row(s) detected.")

    return warnings


# ── Rendering ─────────────────────────────────────────────────────────────────

_SEP = "=" * 58
_DASH = "  " + "-" * 42


def render_report(
    profiles: List[Dict[str, Any]],
    row_count: int,
    warnings: List[str],
) -> None:
    """Print the full profile report to stdout."""
    print(f"\n{_SEP}")
    print("  CSV DATA PROFILE REPORT")
    print(_SEP)
    print(f"  Rows   : {row_count}")
    print(f"  Columns: {len(profiles)}")
    print(_SEP)

    for p in profiles:
        print(f"\n  Column : {p['name']}")
        print(f"  Type   : {p['type']}")
        print(f"  Nulls  : {p['null_count']} ({p['null_pct']:.1%})")
        print(f"  Unique : {p['unique_count']}")

        if "min" in p:
            print(f"  Min    : {p['min']:.6g}")
            print(f"  Max    : {p['max']:.6g}")
            print(f"  Mean   : {p['mean']:.6g}")
            print(f"  Median : {p['median']:.6g}")
            print(f"  StdDev : {p['stdev']:.6g}")
        elif "top_values" in p and p["top_values"]:
            top = ",  ".join(f"{v!r}×{c}" for v, c in p["top_values"])
            print(f"  Top    : {top}")

        print(_DASH)

    print()
    if warnings:
        print("  ⚠  WARNINGS")
        for w in warnings:
            print(f"  •  {w}")
    else:
        print("  ✓  No warnings detected.")

    print(f"\n{_SEP}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # ── Read file ──────────────────────────────────────────────────────────
    try:
        headers, rows = read_csv(args.filepath)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error reading file: {exc}", file=sys.stderr)
        return 1

    # ── Header-only file ───────────────────────────────────────────────────
    if not rows:
        print(
            f"Warning: file has a header but no data rows.\n"
            f"Columns found: {', '.join(headers)}",
            file=sys.stderr,
        )
        return 0

    # ── Normalise row lengths ──────────────────────────────────────────────
    col_count = len(headers)

    wide_count = sum(1 for r in rows if len(r) > col_count)
    if wide_count:
        print(
            f"Warning: {wide_count} row(s) have more columns than the header; "
            "extra values ignored.",
            file=sys.stderr,
        )

    # Pad short rows, truncate wide rows
    norm_rows = [
        (row + [""] * col_count)[:col_count] for row in rows
    ]

    # ── Profile each column ────────────────────────────────────────────────
    profiles = [
        profile_column(header, [row[i] for row in norm_rows], args.max_categories)
        for i, header in enumerate(headers)
    ]

    dupe_count = detect_duplicate_rows(norm_rows)
    warnings = generate_warnings(profiles, args.null_threshold, dupe_count)
    render_report(profiles, len(rows), warnings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
