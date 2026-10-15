# Pipeline verification — October 15, 2026

Verified locally with Python 3.13, the repository's requirements, and PostgreSQL
17 in a disposable Docker container. All 17 unittest tests passed, including the
optional private-export test. The existing project database and processed files
were not modified.

## Full-export results

| Check | Result |
| --- | --- |
| Raw records processed | 278,231 |
| Unique PLAY_END records loaded | 172,899 |
| Missing / duplicate Event IDs | 0 / 0 |
| Analytics listening events | 160,417 |
| Missing or invalid durations retained for audit | 5,972 |
| Second load: inserted / updated / unchanged | 0 / 0 / 172,899 |
| SQL analytics count and capped duration vs. Pandas | Exact match |
| Monthly, track, and device event totals | Match eligible source events |
| SQL data-quality report | Executed successfully |

Synthetic tests also verified updated-row handling, ETL audit counts,
transaction rollback, scrub filtering, duration caps, and skip-rate aggregates.

## Fixes made during verification

- Reject blank/whitespace Event IDs and null event types before loading.
- Make missing end reasons produce explicit false classification flags, keeping
  those records available for auditing while excluding them from analytics.
- Round calculated durations to whole milliseconds before database conversion.
  Floating-point artifacts previously caused some durations to lose one
  millisecond during integer conversion; a regression test covers this case.
- Keep missing durations null while setting their listening-event flag to false.

The suite creates and removes its own database. The private export is read only;
no listening records or private source files are included in the test fixtures.
See the README for commands to reproduce these checks. GitHub Actions runs the
synthetic tests with PostgreSQL; private-export verification requires the local
source file and is skipped in CI. The workflow has been added but has not yet
run on GitHub.
