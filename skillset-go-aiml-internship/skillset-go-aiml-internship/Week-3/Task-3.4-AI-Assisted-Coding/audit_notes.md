# Audit Notes — Task 3.4: AI-Assisted Coding

**Project:** CSV Data Profiler CLI  
**Language:** Python 3 (stdlib only)  
**Date:** 2026-10-06

---

## What the AI assistant generated

The AI assistant (Claude) was given the completed spec (`spec.md`) and asked to produce:

1. `csv_profiler.py` — the working application
2. `test_csv_profiler.py` — a full pytest suite
3. A `sample.csv` for manual verification

The spec was written **before** any code was requested. The assistant had no access to existing code; every line was produced from the spec alone.

---

## Review pass — what I checked

| Area | Finding |
|------|---------|
| **Imports** | Only stdlib (`argparse`, `csv`, `os`, `re`, `sys`, `collections`, `statistics`, `typing`). No hidden third-party deps. ✓ |
| **Error handling** | `main()` wraps `read_csv` in a try/except chain. `FileNotFoundError` and `ValueError` are caught separately; a bare `except Exception` handles unforeseen I/O errors. All print to `stderr` and return exit code 1 as specced. ✓ |
| **Path traversal / injection** | The filepath is read-only; it is never executed or passed to a shell. `os.path.exists` + `open()` are safe here. ✓ |
| **Resource leaks** | The `with open(...)` block closes the file handle on every path including exceptions. ✓ |
| **Encoding fallback** | The inner `try/except UnicodeDecodeError` inside the encoding loop correctly re-raises the blanket `ValueError` only after both encodings fail — no silent data corruption. ✓ |
| **Boolean/numeric collision** | `0` and `1` are in `_BOOL_TOKENS`. This means a column of all `0`/`1` integers is typed `boolean`, not `numeric`. **Deliberate trade-off** per spec priority order; documented in code. |
| **`stdev` on a single value** | `statistics.stdev` raises `StatisticsError` for n=1. The guard `if len(nums) > 1 else 0.0` prevents this. ✓ |
| **Duplicate detection memory** | `detect_duplicate_rows` builds a `set` of tuples. For a file with millions of rows this grows O(n); acceptable for a CLI profiler, not for a streaming tool. Noted as a known limitation. |
| **`--null-threshold` boundary** | Warning fires on `> threshold`, not `>=`. One test originally used `"null" not in out` as its assertion, which was too broad — the word "Nulls" appears in every column block. **Fixed** to `"null values" not in out.lower()`. |

---

## What I accepted as-is

- Overall architecture: pure-function modules (`read_csv`, `infer_type`, `profile_column`, `detect_duplicate_rows`, `generate_warnings`, `render_report`) each with a single responsibility. Clean and easy to test individually.
- The encoding fallback loop (`utf-8` → `latin-1`): exactly what the spec asked for.
- The `_try_float` helper stripping commas before `float()` — handles `"1,000"` correctly, matching the spec.
- All 57 tests: structure (class per module, named helpers) and coverage are good.
- The `argparse` CLI: flag names match the spec; `metavar` labels improve `--help` output.

---

## What I changed and why

| Change | Reason |
|--------|--------|
| **Fixed `test_custom_null_threshold` assertion** | The original assertion `"null" not in out.lower()` always failed because "Nulls" appears in every column block. Changed to `"null values" not in out.lower()` to match the specific warning text pattern. This was a test-logic bug, not a code bug. |
| **Added inline comment on boolean/numeric ambiguity** | The code had no explanation for why `{"0","1"}` are in `_BOOL_TOKENS`. Added a docstring note so the next maintainer doesn't silently "fix" it. |
| **Kept `except Exception` broad in `main()`** | The assistant had it narrow (only `OSError`). Changed to `Exception` because unexpected errors from the CSV module (e.g. malformed dialect) should still print a clean message rather than a raw traceback to end-users. |

---

## Known limitations (out of scope for this task)

- Duplicate detection loads all rows into memory (a set of tuples).
- No streaming / chunked reading for very large files.
- Date inference is pattern-only; invalid dates like `2024-99-99` would pass.
- Only two encoding fallbacks; CJK files encoded in GBK or Shift-JIS will fail.

---

## Key Learnings

1. **Write the spec first, not after.** Having a concrete spec before prompting produced code that matched intent from the first generation. Without it, the assistant would have invented its own assumptions about what "profile" means — which columns to compute, which edge cases to handle, what the exit codes should be. The spec cut the review surface dramatically.

2. **Test assertions can be subtler than the code they test.** The one failing test (`test_custom_null_threshold`) had correct *intent* but an assertion that was too broad — checking that the word "null" didn't appear in output, without realising "Nulls" is a column stat label that always appears. Reviewing tests as critically as production code is not optional.

3. **AI-generated code tends to be correct on the happy path and weak on boundary collisions.** The boolean/numeric overlap (`"0"` and `"1"` qualifying as both) was silently correct per the spec's priority order, but nothing in the code explained it. When two inference rules could fire on the same input, the code's silence is a maintenance hazard. Adding a comment here took five seconds and prevents a future "bug fix" that breaks an intentional decision.

4. **Architectural review is more valuable than line-by-line review.** The assistant produced well-structured pure functions that were individually unit-testable. That structural choice made the tests straightforward and the code easy to verify. The most important review question was "is this the right decomposition?" — everything else followed from it.

5. **Error handling is where AI-generated code needs the most scrutiny.** The initial `except OSError` in `main()` was too narrow; CSV parsing errors from the standard library are raised as `csv.Error`, not `OSError`. Without testing that path I would have shipped a tool that could still show a raw traceback to users for malformed CSV files. Always test the failure paths, not just the happy path.
