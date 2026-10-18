# Power BI verification — October 17, 2026

[Open the private Music Insights report](https://app.powerbi.com/groups/me/reports/ed93d718-12bd-4fb1-8cc1-0b050685c7d6/a39a3783ca53db511264?experience=power-bi).
Access requires an authorized Power BI account; the report is not public.

## Saved web report

| Page | Visuals | Contents |
| --- | ---: | --- |
| Listening overview | 13 | Four KPIs, monthly hours, device hours, three coverage cards, two slicers, heading and note |
| Track explorer | 6 | Top-track chart, track detail table, two slicers, heading and note |
| Devices & data coverage | 10 | Four KPIs, device table, monthly skip trend, two slicers, heading and note |

The semantic model contains 160,417 eligible events and 16 measures. This is a
manual CSV snapshot uploaded October 16; subsequent database loads do not
refresh the online report automatically.

## Checks performed

- Saved each page and reopened the report to check persistence.
- Reopened all three pages; charts/tables loaded without a visible visual error.
- Confirmed that the track chart renders 15 bars for the current snapshot.
- Confirmed that the track table totals show 160,417 events, 3,472.1 hours,
  19.4% skipped, and 44.2% average completion (display rounding).
- Compared all four device chart values with SQL, including the unrounded
  accessible chart values. Device table counts total 160,417.
- Verified date and device synchronization is enabled and visible on all pages.
- Selected MACINTOSH: 1,375 events, 49.08 hours, 9.6% skip rate, 85 undated events.
- Combined MACINTOSH with August 1–31, 2025: 47 events, 1.75 hours, 34 unique
  tracks, 21.3% skip rate, zero undated events, and 100% date coverage.
  Checked those selections carried from the device page to the overview.
- Cleared both slicers and confirmed all-time totals returned before saving.
- Confirmed the device page shows 27.7% natural-end rate, 44.2% average
  completion, 56,679 undated events in its table, and 64.7% date coverage.

Run `sql/powerbi_checks.sql` to reproduce the SQL comparisons. SQL retains two
decimal places; report percentages use one decimal and cards may abbreviate
large counts with K. Tables retain exact event counts.

## Visual review completed

Browser screenshots became available again on October 17. Inspected screenshots
of all three saved report pages at fit-to-page (55%). Headings, slicers, cards,
charts, and footer notes rendered without overlapping containers. Long track
labels truncate within the chart; the detail tables provide horizontal and
vertical scrollbars for their wider content. Some screenshots reflect active
reader filters rather than the default all-time view.

Screenshots contain private listening history and remain local, outside Git.
This was a desktop browser review; mobile and exhaustive tooltip/accessibility
checks were not performed.

## Remaining platform checks

The separate local Desktop project still requires Windows Power BI Desktop to
open, refresh PostgreSQL, and verify its visuals. Local schema validation does
not replace that engine check. Mobile layout, scheduled refresh, and public
publishing have not been configured.
