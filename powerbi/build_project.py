"""Build a data-free native Power BI project using the public PBIR format.

Run from any directory: python powerbi/build_project.py
No credentials or private listening records are embedded in the output.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "MusicInsights.Report"
MODEL = ROOT / "MusicInsights.SemanticModel"
FABRIC = "https://developer.microsoft.com/json-schemas/fabric/"
DEFINITION = FABRIC + "item/report/definition/"
TABLE = "Listening Events"
COLORS = {
    "background": "#0B1020",
    "panel": "#151E32",
    "text": "#EEF2FF",
    "muted": "#A8B5CE",
    "accent": "#2DD4BF",
}
COLUMNS = [
    ("Event ID", "event_id", "string"),
    ("Listening Date", "listening_date", "dateTime"),
    ("Listening Month", "listening_month", "dateTime"),
    ("Month", "month_label", "string"),
    ("Month Sort", "month_sort", "int64"),
    ("Track Name", "song_name", "string"),
    ("Album", "album_name", "string"),
    ("Track", "track_label", "string"),
    ("Track Key", "track_key", "string"),
    ("Device", "device_type", "string"),
    ("Listening Duration ms", "listening_duration_ms", "int64"),
    ("Is Skipped", "is_skipped", "boolean"),
    ("Is Natural End", "is_natural_end", "boolean"),
    ("Completion Percent", "completion_percent", "double"),
    ("Has Listening Date", "has_listening_date", "boolean"),
]
MEASURES = {
    "Listening Events": ("COALESCE(COUNTROWS('Listening Events'), 0)", "#,0"),
    "Listening Hours": (
        "DIVIDE(SUM('Listening Events'[Listening Duration ms]), 3600000)",
        "#,0.0",
    ),
    "Listening Minutes": (
        "DIVIDE(SUM('Listening Events'[Listening Duration ms]), 60000)",
        "#,0.00",
    ),
    "Unique Tracks": ("DISTINCTCOUNT('Listening Events'[Track Key])", "#,0"),
    "Skipped Events": (
        "COALESCE(CALCULATE(COUNTROWS('Listening Events'), KEEPFILTERS('Listening Events'[Is Skipped] = TRUE())), 0)",
        "#,0",
    ),
    "Skip Rate": ("DIVIDE([Skipped Events], [Listening Events])", "0.0%"),
    "Natural End Events": (
        "COALESCE(CALCULATE(COUNTROWS('Listening Events'), KEEPFILTERS('Listening Events'[Is Natural End] = TRUE())), 0)",
        "#,0",
    ),
    "Natural End Rate": ("DIVIDE([Natural End Events], [Listening Events])", "0.0%"),
    "Dated Events": (
        "COALESCE(CALCULATE(COUNTROWS('Listening Events'), KEEPFILTERS('Listening Events'[Has Listening Date] = TRUE())), 0)",
        "#,0",
    ),
    "Events Without Dates": (
        "COALESCE(CALCULATE(COUNTROWS('Listening Events'), KEEPFILTERS('Listening Events'[Has Listening Date] = FALSE())), 0)",
        "#,0",
    ),
    "Date Coverage": ("DIVIDE([Dated Events], [Listening Events])", "0.0%"),
    "Dated Listening Hours": (
        "CALCULATE([Listening Hours], KEEPFILTERS('Listening Events'[Has Listening Date] = TRUE()))",
        "#,0.0",
    ),
    "Dated Skip Rate": (
        "CALCULATE([Skip Rate], KEEPFILTERS('Listening Events'[Has Listening Date] = TRUE()))",
        "0.0%",
    ),
    "Average Completion": (
        "DIVIDE(AVERAGE('Listening Events'[Completion Percent]), 100)",
        "0.0%",
    ),
    "Track Rank": (
        "RANKX(ALLSELECTED('Listening Events'[Track]), [Listening Hours], , DESC, DENSE)",
        "#,0",
    ),
    "Top Track Hours": ("IF([Track Rank] <= 15, [Listening Hours])", "#,0.0"),
}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def literal(value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    elif isinstance(value, (int, float)):
        value = str(value) + "D"
    else:
        value = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": value}}}


def color(value):
    return {"solid": {"color": literal(value)}}


def field(name, measure=False):
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": TABLE}},
            "Property": name,
        }
    }


def projection(name, measure=False):
    return {
        "field": field(name, measure),
        "queryRef": f"{TABLE}.{name}",
        "nativeQueryRef": name,
    }


def visual(page, name, kind, title, x, y, width, height, roles=None, sort=None):
    config = {
        "visualType": kind,
        "visualContainerObjects": {
            "title": [
                {
                    "properties": {
                        "show": literal(bool(title)),
                        "text": literal(title),
                        "fontColor": color(COLORS["text"]),
                        "fontSize": literal(12),
                        "fontFamily": literal("Segoe UI Semibold"),
                    }
                }
            ],
            "background": [
                {
                    "properties": {
                        "show": literal(True),
                        "color": color(COLORS["panel"]),
                        "transparency": literal(0),
                    }
                }
            ],
            "border": [{"properties": {"show": literal(False)}}],
        },
    }
    if roles:
        config["query"] = {
            "queryState": {
                role: {"projections": [projection(n, m) for n, m in values]}
                for role, values in roles.items()
            }
        }
        if sort:
            config["query"]["sortDefinition"] = {
                "sort": [{"field": field(sort[0], sort[1]), "direction": sort[2]}]
            }
    result = {
        "$schema": DEFINITION + "visualContainer/2.1.0/schema.json",
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": 0,
            "height": height,
            "width": width,
            "tabOrder": y * 10 + x,
        },
        "visual": config,
    }
    return result


def save_visual(page, result):
    write(
        REPORT / "definition/pages" / page / "visuals" / result["name"] / "visual.json",
        result,
    )


def text(page, name, content, x, y, width, height, size=12, muted=False):
    result = visual(page, name, "textbox", "", x, y, width, height)
    result["visual"]["objects"] = {
        "general": [
            {
                "properties": {
                    "paragraphs": [
                        {
                            "textRuns": [
                                {
                                    "value": content,
                                    "textStyle": {
                                        "fontFamily": "Segoe UI",
                                        "fontSize": f"{size}pt",
                                        "color": COLORS["muted" if muted else "text"],
                                    },
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }
    result["visual"]["visualContainerObjects"]["background"][0]["properties"][
        "show"
    ] = literal(False)
    save_visual(page, result)


def card(page, name, measure, title, x, y, width=326, height=112):
    result = visual(
        page, name, "card", title, x, y, width, height, {"Values": [(measure, True)]}
    )
    result["visual"]["objects"] = {
        "labels": [
            {
                "properties": {
                    "color": color(COLORS["accent"]),
                    "fontSize": literal(30),
                    "labelDisplayUnits": literal(1),
                }
            }
        ],
        "categoryLabels": [{"properties": {"show": literal(False)}}],
    }
    save_visual(page, result)


def slicer(page, name, column, title, x, width):
    result = visual(
        page, name, "slicer", title, x, 112, width, 78, {"Values": [(column, False)]}
    )
    result["visual"]["objects"] = {
        "data": [
            {
                "properties": {
                    "mode": literal(
                        "Between" if column == "Listening Date" else "Dropdown"
                    )
                }
            }
        ]
    }
    result["visual"]["syncGroup"] = {
        "groupName": name,
        "fieldChanges": True,
        "filterChanges": True,
    }
    save_visual(page, result)


def build():
    write(
        ROOT / "MusicInsights.pbip",
        {
            "$schema": FABRIC + "pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "MusicInsights.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write(
        REPORT / "definition.pbir",
        {
            "$schema": FABRIC + "item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../MusicInsights.SemanticModel"}},
        },
    )
    write(
        MODEL / "definition.pbism",
        {
            "$schema": FABRIC
            + "item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "1.0",
            "settings": {},
        },
    )
    columns = []
    for name, source, kind in COLUMNS:
        column = {
            "name": name,
            "sourceColumn": source,
            "dataType": kind,
            "summarizeBy": "none",
        }
        if name in {
            "Event ID",
            "Track Key",
            "Month Sort",
            "Listening Duration ms",
            "Is Skipped",
            "Is Natural End",
            "Has Listening Date",
            "Completion Percent",
        }:
            column["isHidden"] = True
        if kind == "dateTime":
            column["formatString"] = "yyyy-MM-dd"
        if name == "Month":
            column["sortByColumn"] = "Month Sort"
        columns.append(column)
    write(
        MODEL / "model.bim",
        {
            "name": "MusicInsights",
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "dataAccessOptions": {
                    "legacyRedirects": True,
                    "returnErrorValuesAsNull": True,
                },
                "expressions": [
                    {
                        "name": "PostgreSQL Server",
                        "kind": "m",
                        "expression": '"localhost:5432" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    },
                    {
                        "name": "PostgreSQL Database",
                        "kind": "m",
                        "expression": '"music_insights" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    },
                ],
                "tables": [
                    {
                        "name": TABLE,
                        "columns": columns,
                        "measures": [
                            {
                                "name": name,
                                "expression": expression,
                                "formatString": fmt,
                                "displayFolder": "Listening metrics",
                            }
                            for name, (expression, fmt) in MEASURES.items()
                        ],
                        "partitions": [
                            {
                                "name": TABLE,
                                "mode": "import",
                                "source": {
                                    "type": "m",
                                    "expression": [
                                        "let",
                                        '    Source = PostgreSQL.Database(#"PostgreSQL Server", #"PostgreSQL Database", [CreateNavigationProperties=false]),',
                                        '    Events = Source{[Schema="analytics",Item="powerbi_listening_events"]}[Data]',
                                        "in",
                                        "    Events",
                                    ],
                                },
                            }
                        ],
                    }
                ],
                "annotations": [
                    {
                        "name": "PBI_QueryOrder",
                        "value": json.dumps(
                            ["PostgreSQL Server", "PostgreSQL Database", TABLE]
                        ),
                    }
                ],
            },
        },
    )
    (ROOT / "measures.dax").write_text(
        "// Create these measures on the 'Listening Events' table in the web model.\n// Each block is a separate measure; percentage measures use percentage formatting.\n\n"
        + "\n\n".join(
            f"// Format: {fmt}\n{name} =\n{expression}"
            for name, (expression, fmt) in MEASURES.items()
        )
        + "\n"
    )
    (ROOT / "web_measures.tmdl").write_text(
        "createOrReplace\n\n\tref table 'Listening Events'\n"
        + "".join(
            f"\n\t\tmeasure '{name}' = {expression}\n"
            f"\t\t\tformatString: {fmt}\n"
            "\t\t\tdisplayFolder: Listening metrics\n"
            for name, (expression, fmt) in MEASURES.items()
        )
    )
    theme = {
        "name": "Music Insights",
        "dataColors": [
            "#2DD4BF",
            "#A78BFA",
            "#60A5FA",
            "#FBBF24",
            "#FB7185",
            "#34D399",
        ],
        "background": COLORS["background"],
        "foreground": COLORS["text"],
        "tableAccent": COLORS["accent"],
        "visualStyles": {
            "*": {
                "*": {
                    "background": [
                        {
                            "color": {"solid": {"color": COLORS["panel"]}},
                            "transparency": 0,
                        }
                    ],
                    "title": [
                        {
                            "color": {"solid": {"color": COLORS["text"]}},
                            "fontFamily": "Segoe UI",
                            "fontSize": 12,
                        }
                    ],
                    "categoryAxis": [
                        {"labelColor": {"solid": {"color": COLORS["muted"]}}}
                    ],
                    "valueAxis": [
                        {"labelColor": {"solid": {"color": COLORS["muted"]}}}
                    ],
                }
            }
        },
    }
    write(REPORT / "StaticResources/RegisteredResources/MusicInsights.json", theme)
    write(
        REPORT / "definition/version.json",
        {
            "$schema": DEFINITION + "versionMetadata/1.0.0/schema.json",
            "version": "3.3.0",
        },
    )
    write(
        REPORT / "definition/report.json",
        {
            "$schema": DEFINITION + "report/1.0.0/schema.json",
            "layoutOptimization": "None",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": "5.55",
                    "type": "SharedResources",
                },
                "customTheme": {
                    "name": "MusicInsights",
                    "reportVersionAtImport": "5.55",
                    "type": "RegisteredResources",
                },
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {
                            "name": "MusicInsights",
                            "path": "MusicInsights.json",
                            "type": "CustomTheme",
                        }
                    ],
                }
            ],
        },
    )
    pages = [
        ("overview", "01 · Listening overview"),
        ("tracks", "02 · Track explorer"),
        ("devices", "03 · Devices & data coverage"),
    ]
    write(
        REPORT / "definition/pages/pages.json",
        {
            "$schema": DEFINITION + "pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p for p, _ in pages],
            "activePageName": "overview",
        },
    )
    for page, title in pages:
        write(
            REPORT / "definition/pages" / page / "page.json",
            {
                "$schema": DEFINITION + "page/2.0.0/schema.json",
                "name": page,
                "displayName": title,
                "displayOption": "FitToPage",
                "height": 900,
                "width": 1440,
                "objects": {
                    "background": [
                        {
                            "properties": {
                                "color": color(COLORS["background"]),
                                "transparency": literal(0),
                            }
                        }
                    ]
                },
            },
        )
        text(
            page,
            "heading",
            "MUSIC INSIGHTS  /  " + title[5:].upper(),
            32,
            20,
            1376,
            56,
            26,
        )
        text(
            page,
            "subheading",
            "Your Apple Music listening history, backed by verified playback events.",
            32,
            76,
            1376,
            28,
            11,
            True,
        )
        slicer(
            page,
            "listening_date",
            "Listening Date",
            "Listening date · clear for all-time totals",
            32,
            660,
        )
        slicer(page, "device", "Device", "Device", 716, 692)
        text(
            page,
            "coverage_note",
            "Monthly charts use dated events only. All-time totals include undated events; choosing a date range excludes them.\nFilters sync across pages. Clear the date filter to inspect full data coverage. Plays are playback events, not unique songs.",
            32,
            830,
            1376,
            58,
            10,
            True,
        )
    for index, (measure, title) in enumerate(
        [
            ("Listening Hours", "Listening hours"),
            ("Listening Events", "Playback events"),
            ("Unique Tracks", "Unique tracks · song + album"),
            ("Skip Rate", "Skip rate"),
        ]
    ):
        card("overview", "kpi_" + str(index), measure, title, 32 + index * 350, 214)
    save_visual(
        "overview",
        visual(
            "overview",
            "monthly_hours",
            "lineChart",
            "Listening hours by month · dated events",
            32,
            350,
            860,
            340,
            {"Category": [("Month", False)], "Y": [("Dated Listening Hours", True)]},
            ("Month", False, "Ascending"),
        ),
    )
    save_visual(
        "overview",
        visual(
            "overview",
            "device_hours",
            "clusteredBarChart",
            "Listening hours by device",
            916,
            350,
            492,
            340,
            {"Category": [("Device", False)], "Y": [("Listening Hours", True)]},
            ("Listening Hours", True, "Descending"),
        ),
    )
    card(
        "overview",
        "dated_events",
        "Dated Events",
        "Events with a listening date",
        32,
        714,
        440,
        96,
    )
    card(
        "overview",
        "undated_events",
        "Events Without Dates",
        "Events without a listening date",
        496,
        714,
        440,
        96,
    )
    card(
        "overview", "date_coverage", "Date Coverage", "Date coverage", 960, 714, 448, 96
    )
    save_visual(
        "tracks",
        visual(
            "tracks",
            "top_tracks",
            "clusteredBarChart",
            "Top 15 track ranks by listening hours · ties included",
            32,
            214,
            800,
            596,
            {"Category": [("Track", False)], "Y": [("Top Track Hours", True)]},
            ("Top Track Hours", True, "Descending"),
        ),
    )
    save_visual(
        "tracks",
        visual(
            "tracks",
            "track_table",
            "tableEx",
            "Track details · select a bar to inspect",
            856,
            214,
            552,
            596,
            {
                "Values": [
                    ("Track Name", False),
                    ("Album", False),
                    ("Listening Events", True),
                    ("Listening Hours", True),
                    ("Skip Rate", True),
                    ("Average Completion", True),
                ]
            },
            ("Listening Hours", True, "Descending"),
        ),
    )
    for index, (measure, title) in enumerate(
        [
            ("Natural End Rate", "Natural completion rate"),
            ("Average Completion", "Average track completion"),
            ("Events Without Dates", "Events without dates"),
            ("Date Coverage", "Date coverage"),
        ]
    ):
        card("devices", "kpi_" + str(index), measure, title, 32 + index * 350, 214)
    save_visual(
        "devices",
        visual(
            "devices",
            "device_details",
            "tableEx",
            "Device breakdown",
            32,
            350,
            760,
            460,
            {
                "Values": [
                    ("Device", False),
                    ("Listening Events", True),
                    ("Listening Hours", True),
                    ("Skip Rate", True),
                    ("Natural End Rate", True),
                ]
            },
            ("Listening Hours", True, "Descending"),
        ),
    )
    save_visual(
        "devices",
        visual(
            "devices",
            "monthly_skip_rate",
            "lineChart",
            "Skip rate by month · dated events",
            816,
            350,
            592,
            460,
            {"Category": [("Month", False)], "Y": [("Dated Skip Rate", True)]},
            ("Month", False, "Ascending"),
        ),
    )
    print(
        "Built MusicInsights.pbip: 3 pages, PostgreSQL import model, and DAX measures."
    )


if __name__ == "__main__":
    build()
