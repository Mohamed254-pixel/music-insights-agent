"""Check report bindings/layout; optionally validate Microsoft's JSON schemas.

python powerbi/validate_project.py --schemas
Schema validation requires: pip install -r requirements-dev.txt
This checks metadata, not execution of DAX/M or rendering in Power BI.
"""

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "MusicInsights.Report"
MODEL = ROOT / "MusicInsights.SemanticModel"


def read(path):
    return json.loads(path.read_text())


def validate_project(schemas=False):
    model = read(MODEL / "model.bim")["model"]
    tables = {table["name"]: table for table in model["tables"]}
    pages_root = REPORT / "definition/pages"
    metadata = read(pages_root / "pages.json")
    assert metadata["activePageName"] in metadata["pageOrder"]
    count = 0
    for page_name in metadata["pageOrder"]:
        page_path = pages_root / page_name
        page = read(page_path / "page.json")
        assert page["name"] == page_name
        names = set()
        for path in sorted((page_path / "visuals").glob("*/visual.json")):
            visual = read(path)
            assert visual["name"] == path.parent.name
            assert visual["name"] not in names
            names.add(visual["name"])
            position = visual["position"]
            assert 0 <= position["x"] <= page["width"] - position["width"]
            assert 0 <= position["y"] <= page["height"] - position["height"]
            for role in (
                visual["visual"].get("query", {}).get("queryState", {}).values()
            ):
                for projection in role["projections"]:
                    kind, expression = next(iter(projection["field"].items()))
                    table = tables[expression["Expression"]["SourceRef"]["Entity"]]
                    fields = table["measures" if kind == "Measure" else "columns"]
                    assert expression["Property"] in {item["name"] for item in fields}
            count += 1
    project = read(ROOT / "MusicInsights.pbip")
    assert (ROOT / project["artifacts"][0]["report"]["path"]).is_dir()
    reference = read(REPORT / "definition.pbir")["datasetReference"]["byPath"]["path"]
    assert (REPORT / reference).resolve() == MODEL.resolve()
    for table in tables.values():
        column_names = {column["name"] for column in table["columns"]}
        for column in table["columns"]:
            if "sortByColumn" in column:
                assert column["sortByColumn"] in column_names
    schema_count = 0
    if schemas:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT7

        cache = {}

        def retrieve(uri):
            assert urllib.parse.urlparse(uri).hostname == "developer.microsoft.com", uri
            if uri not in cache:
                with urllib.request.urlopen(uri, timeout=30) as response:
                    document = json.load(response)
                cache[uri] = Resource.from_contents(
                    document, default_specification=DRAFT7
                )
            return cache[uri]

        registry = Registry(retrieve=retrieve)
        for path in sorted(ROOT.rglob("*")):
            if path.suffix not in {".json", ".pbip", ".pbir", ".pbism"}:
                continue
            document = read(path)
            uri = document.get("$schema")
            if not uri:
                continue
            schema = retrieve(uri).contents
            errors = list(
                Draft7Validator(schema, registry=registry).iter_errors(document)
            )
            if errors:
                detail = "\n".join(
                    f"{list(error.path)}: {error.message}" for error in errors
                )
                raise ValueError(f"{path.relative_to(ROOT)}:\n{detail}")
            schema_count += 1
    print(
        f"Validated {len(metadata['pageOrder'])} pages, {count} visuals, model bindings and layout."
    )
    if schemas:
        print(
            f"Validated {schema_count} files against Microsoft's published JSON schemas."
        )
    print(
        "Power BI must still load/refresh the model and render the report for final acceptance."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", action="store_true")
    validate_project(parser.parse_args().schemas)
