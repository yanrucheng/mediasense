"""Read-only packet shape and synthetic vector checks; not a runtime test."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent


def identity(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def check_observations(value):
    if isinstance(value, dict):
        if "name" in value and "status" in value:
            assert (value["status"] == "available") == ("value" in value)
            if value["status"] == "failed":
                assert "basis" in value
        for child in value.values():
            check_observations(child)
    elif isinstance(value, list):
        for child in value:
            check_observations(child)


def main():
    validators = {}
    for tool in ("run", "read"):
        contract = json.loads((ROOT / "contracts" / f"precheck-{tool}.tool.json").read_text())
        for side in ("inputSchema", "outputSchema"):
            schema = contract[side]
            Draft202012Validator.check_schema(schema)
            validators[tool, side] = Draft202012Validator(schema, format_checker=FormatChecker())
        for action, fragment in contract["responseSchemas"].items():
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": contract["outputSchema"]["$defs"],
                **fragment,
            }
            Draft202012Validator.check_schema(schema)
            validators[tool, f"response:{action}"] = Draft202012Validator(schema, format_checker=FormatChecker())
    examples = json.loads((ROOT / "contracts/examples.json").read_text())
    actions = set()
    for case in examples["exchanges"]:
        tool, request, response = case["tool"], case["request"], case["response"]
        for side, data in (("inputSchema", request), ("outputSchema", response)):
            errors = list(validators[tool, side].iter_errors(data))
            assert not errors, f'{case["name"]} {side}: ' + "; ".join(e.message for e in errors)
        actions.add((tool, request["action"]))
        validators[tool, f'response:{request["action"]}'].validate(response)
        check_observations(response)
        if "resolution" in response:
            refs = [m["source_item_ref"] for m in response["members"]]
            assert refs == sorted(set(refs))
            assert response["page"]["total"] == len(refs)
            assert response["resolution"]["source_set_identity"] == identity(request["source_set"])
            assert response["resolution"]["membership_identity"] == identity({
                "result_ref": request["result_ref"], "source_set": request["source_set"], "members": refs
            })
        if "accounting" in response and "routes" in response["accounting"]:
            accounting = response["accounting"]
            assert sum(accounting["routes"].values()) == accounting["total"]
            assert sum(row["count"] for row in accounting["scope_condition"]) == accounting["total"]
        for group in response.get("coordinate_groups", []):
            for counts in group["components"].values():
                assert sum(counts.values()) == group["member_count"]
    assert actions == {("run", a) for a in ("start", "status", "pause", "resume", "cancel")} | {
        ("read", a) for a in ("review", "expand", "resolve", "geo_summary")
    }
    for case in examples["negative"]:
        assert not validators[case["tool"], case["side"]].is_valid(case["value"]), case["name"]
    for link in ("proposal.md", "design.md", "tasks.md", "README.md"):
        assert (ROOT / link).is_file()
    print(f'PASS: 2 contracts; {len(actions)} actions; {len(examples["exchanges"])} positive and '
          f'{len(examples["negative"])} negative vectors; action-bound responses; exact membership hashes.')


if __name__ == "__main__":
    main()
