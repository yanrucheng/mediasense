"""Verify the stable contract home and synchronized release snapshots."""

import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "docs/spec/contract"
FAMILIES = {
    "manufacturer-knowledge",
    "precheck-read",
    "precheck-run",
    "geo-query",
    "dataset-open",
    "plan-work",
    "frozen-plan",
    "default-organization-profile",
    "apply",
}


def test_single_stable_contract_home_and_historical_redirects():
    assert {p.name for p in CONTRACT.iterdir() if p.is_dir()} == FAMILIES
    for name in FAMILIES:
        assert (CONTRACT / name / "index.md").is_file()
        assert (
            "status: active"
            in (CONTRACT / name / "index.md").read_text().split("---")[1]
        )
    for path in (ROOT / "docs/spec").glob("spec-*/index.md"):
        frontmatter = path.read_text().split("---")[1]
        assert "status: superseded" in frontmatter
        assert 'superseded-by: ""' not in frontmatter
        assert "contract/" in path.read_text()
    assert "docs/spec/contract/index.md" in (ROOT / "AGENTS.md").read_text()


def test_all_canonical_schemas_compile_and_local_references_resolve():
    for path in CONTRACT.rglob("*.json"):
        value = json.loads(path.read_text())
        schemas = []
        if path.name.endswith(".tool.json"):
            schemas = [value["inputSchema"], value["outputSchema"]]
            for fragment in value.get("responseSchemas", {}).values():
                schemas.append({"$defs": value["outputSchema"]["$defs"], **fragment})
        elif path.name.endswith(".schema.json"):
            schemas = [value]
        for schema in schemas:
            Draft202012Validator.check_schema(schema)
            for target in re.findall(r'"\$ref":\s*"(#/[^"]+)"', json.dumps(schema)):
                current = schema
                for key in target[2:].split("/"):
                    current = current[key.replace("~1", "/").replace("~0", "~")]


def test_all_exchange_contracts_match_release_snapshots():
    released = ROOT / "src/mediasense/_resources/contracts"
    for path in CONTRACT.rglob("*.json"):
        if not path.name.endswith((".tool.json", ".schema.json")):
            continue
        assert json.loads(path.read_text()) == json.loads(
            (released / path.name).read_text()
        )


def test_contract_docs_have_resolvable_local_links_and_unique_ids():
    seen = set()
    for path in CONTRACT.rglob("*.md"):
        text = path.read_text()
        frontmatter = text.split("---")[1]
        doc_id = re.search(r'^id: "([^"]+)"', frontmatter, re.M).group(1)
        assert doc_id not in seen
        seen.add(doc_id)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"^\w+:", target) or target.startswith("#"):
                continue
            destination = target.split("#", 1)[0]
            assert (path.parent / destination).resolve().exists(), (path, target)
