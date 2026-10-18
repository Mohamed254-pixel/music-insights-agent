# Music Insights Power BI report

The native project contains three report pages, 32 visuals, 16 DAX measures,
and a PostgreSQL import model. The native metadata has been schema-checked; the Desktop project has not yet
been opened, refreshed, or visually verified in Power BI Desktop. A separate
private web semantic model has been imported, its 16 measures applied, and the
summary results checked against SQL. The separate web report now has three
saved pages and 29 visuals. Its date/device slicers sync across all pages and
passed combined-filter checks.

The web report was reloaded to verify that the pages, charts, tables, and
headings persisted. Screenshot review passed for all three pages on October 17 after browser
capture became available again. Wide tables use horizontal scrolling. The local three-page definitions
remain a separate 32-visual Desktop project, not an export of the web report.
See [verification.md](verification.md) for the saved report link and checks.

## Pages

| Page | Contents |
| --- | --- |
| Listening overview | Listening hours, playback events, unique tracks, skip rate, monthly hours, device hours, and date coverage |
| Track explorer | Top 15 track ranks by hours (including ties), track/album details, skip rates, and completion |
| Devices & data coverage | Device breakdown, monthly skip rate, natural completion rate, and missing-date indicators |

Each page has date and device slicers configured to sync across the report.
All metrics use the same event-level table, so a device/date selection also
filters track rankings and KPIs. Skip rates are calculated from event counts
in the current selection, never by averaging monthly percentages.

## Mac: Power BI web workflow

Use the Power BI service in your browser. Your school account must be able to
create semantic models and reports, and its administrator must allow web model
editing. If sign-in requires school verification or MFA, complete that yourself.
No school credentials belong in this repository.

1. Apply `sql/powerbi_view.sql` to the existing PostgreSQL database after the
   existing schema and analytics views have been created:

   ```bash
   docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
     -U music_user -d music_insights < sql/powerbi_view.sql
   ```

2. With your local `.env` configured, export the private snapshot:

   ```bash
   python src/export_powerbi.py
   ```

   The default output is `data/processed/Listening Events.csv`, ignored by Git.
   It contains analytics-eligible playback events, with capped durations and
   explicit missing-date flags. It does not contain account identifiers,
   geographic information, IP addresses, or device identifiers. Treat the
   listening history itself as private.

3. In Power BI, open your private workspace and select **New item → Semantic
   model → CSV → Upload file**. In some tenants, the entry is **Create → Get
   data → Text/CSV**. Upload `Listening Events.csv`, use UTF-8 encoding, and
   select **Create a semantic model only**. Name the model **Music Insights**
   and the table **Listening Events**.

4. Check types before creating the report:

   | Columns | Type |
   | --- | --- |
   | Listening Date, Listening Month | Date |
   | Listening Duration ms, Month Sort | Whole number |
   | Is Skipped, Is Natural End, Has Listening Date | True/false |
   | Completion Percent | Decimal number |
   | Event ID, Track Key, other text columns | Text |

   Keep empty dates null. Sort **Month** by **Month Sort**. If your tenant
   supports web model editing, create the measures in `measures.dax` one at a
   time on **Listening Events** and apply the format noted above each measure.
   Hide the ID, key, raw duration, raw percentage, sort, and boolean helper
   columns from report authors after adding the measures.

5. Create a report from the semantic model. The page layout and field bindings
   are defined under `MusicInsights.Report/definition/pages/`; use the table
   above as the authoring guide and import the theme from
   `MusicInsights.Report/StaticResources/RegisteredResources/MusicInsights.json`.
   The local PBIP file is a Desktop project, not a CSV or a web-upload report.
   Uploading the CSV creates the data model; it does not automatically install
   the PBIR pages or DAX measures.

6. Run `sql/powerbi_checks.sql` and compare all cards/charts with SQL. Check date
   and device slicers together, tied track ranks, and the missing-date figures.
   Keep the report private; no public publishing is configured.

The snapshot is a manual refresh workflow. Re-export after loading a new Apple
Music export, then update the cloud source/model. The Power BI service cannot
reach this Mac's `localhost:5432` directly. A hosted database or supported gateway
would be a separate refresh setup; none has been installed or configured.

Microsoft's current documentation describes [CSV semantic-model import](https://learn.microsoft.com/en-us/power-bi/connect-data/service-comma-separated-value-files)
and [web model editing, measures, and tenant permissions](https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models).

## Native Desktop project

`MusicInsights.pbip` opens the included report and semantic model in Power BI
Desktop on Windows. Its import query reads
`analytics.powerbi_listening_events` using configurable **PostgreSQL Server**
and **PostgreSQL Database** parameters. Defaults are `localhost:5432` and
`music_insights`; use the database host reachable from the Windows machine or VM.
Enter database credentials in Power BI's connection dialog, not in model files.

No data cache is bundled, so first opening requires a refresh. Local caches,
`.pbix`, and `.pbit` files are ignored to avoid committing listening records.
The semantic model uses the supported JSON `model.bim` format; report definitions
use Microsoft's documented [PBIR format](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report).

## Definitions and date coverage

- **Playback events:** eligible PLAY_END sessions; a repeat session counts again.
- **Listening hours:** summed capped listening duration divided by 3,600,000.
- **Unique tracks:** distinct normalized song-and-album pairs, not song name alone.
- **Skip rate:** skipped eligible events divided by all eligible events.
- **Natural completion rate:** natural-end events divided by eligible events.
- **Average completion:** average event completion percentage, displayed as a percentage.
- **Date coverage:** eligible events with a local listening date divided by all eligible events.

The view keeps undated events. Clearing date filters includes them in all-time
KPIs and device/track summaries. Monthly charts use dated events only, and a date
range excludes undated events from every measure. Dates are never invented or
inferred from unrelated timestamps.

## Local verification — October 16, 2026

The existing database snapshot produced these SQL values before report rendering:

| Metric | Value |
| --- | ---: |
| Playback events | 160,417 |
| Listening hours | 3,472.07 |
| Unique tracks | 16,723 |
| Skip rate | 19.35% |
| Dated events | 103,738 |
| Undated events | 56,679 |
| Date coverage | 64.67% |

The web model DAX summary was also checked against these SQL values (the query
grid rounded percentage fractions). This does not verify the Desktop refresh or
all report visuals. Source reprocessing can slightly change duration totals after
the millisecond precision fix; compare the report against the same database
snapshot using `sql/powerbi_checks.sql`.

## Development

```bash
python -m pip install -r requirements-dev.txt
python powerbi/build_project.py
python powerbi/validate_project.py --schemas
python -m unittest discover -s tests -t . -v
```

The builder is the source for report/model metadata and `measures.dax`. Regenerate
after editing it; changes made directly in generated files can be overwritten.
The validator checks visual field bindings, page bounds, model references, and
Microsoft's public schemas. It does not execute DAX or Power Query, or render
visuals. PostgreSQL integration tests separately verify the view and CSV export.
The web report acceptance checks are recorded in `verification.md`. The separate
Desktop project still requires a Windows refresh and visual check.
