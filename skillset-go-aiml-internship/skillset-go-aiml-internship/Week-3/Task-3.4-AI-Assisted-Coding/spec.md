# Spec: CSV Data Profiler CLI
**Written before any code was generated — 2026-10-06**

---

## Goal
A command-line tool that reads any CSV file and prints a concise data
profile: column types, null rates, basic stats, and dataset-level warnings.
No external libraries — stdlib only.

---

## Inputs
| Source | Detail |
|--------|--------|
| Positional arg | Path to a `.csv` file |
| `--max-categories N` | How many top values to show for categorical columns (default 5) |
| `--null-threshold F` | Null-ratio that triggers a warning (default 0.20) |

---

## Outputs (stdout)
```
==============================================
  CSV DATA PROFILE REPORT
==============================================
  Rows   : 1000
  Columns: 7
...
  Column : age
  Type   : numeric
  Nulls  : 12 (1.2%)
  Unique : 58
  Min    : 18   Max: 94   Mean: 42.3   StdDev: 15.1
----------------------------------------------
  ⚠  WARNINGS
  • Column 'notes' has 45% null values.
  • 3 duplicate row(s) detected.
==============================================
```

---

## Error cases (must be handled gracefully, no tracebacks)
1. File not found → stderr message + exit 1
2. Empty file (0 bytes) → stderr + exit 1
3. Header row only, no data → warning on stderr + exit 0
4. Non-UTF-8 encoding → retry with `latin-1`; fail with message if still broken
5. Rows shorter than header → pad with empty string
6. Rows wider than header → truncate + warn
7. Column entirely null → type "empty", warn if above threshold

---

## Per-column type inference (priority order)
1. **boolean** — all values in {true/false/yes/no/0/1/t/f/y/n} (case-insensitive)
2. **numeric** — all non-null values parseable as float (commas stripped)
3. **mostly_numeric** — ≥80% parseable as float (warn)
4. **date** — ≥80% match `YYYY-MM-DD` or `DD/MM/YYYY`
5. **categorical** — everything else

---

## Warnings
| Condition | Message |
|-----------|---------|
| null % > threshold | Column 'X' has N% null values. |
| unique_count == 1 | Column 'X' has only one unique value (constant column). |
| type == mostly_numeric | Column 'X' is mostly numeric but has some non-numeric values. |
| duplicate rows > 0 | N duplicate row(s) detected. |

---

## Out of scope
- Writing output to file (stdout only)
- Plotting / charts
- CSV writing / transformation
- Network access
