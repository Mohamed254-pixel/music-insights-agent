# Engineering Decisions and Tradeoffs

## Exact checks for completely missing columns

### Problem

The first profiling version rounded missing percentages to two decimal places. `Source Radio Type` had 278,221 missing values out of 278,231 rows, so it displayed as 100.0% missing even though 10 valid values existed.

### Risk

Using the rounded percentage to remove empty columns could delete a column that still contains valid data.

### Decision

The profiler now records:

- Exact missing count
- Exact non-missing count
- Missing percentage to four decimal places
- An `all_missing` boolean based on exact row counts

Percentages are only used for reporting. Column-removal decisions use the exact `all_missing` value.

### Verification

`Source Radio Type` now reports:

- Missing: 278,221
- Non-missing: 10
- Missing percentage: 99.9964%
- Completely missing: False