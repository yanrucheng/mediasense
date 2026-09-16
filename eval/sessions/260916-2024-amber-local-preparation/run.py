"""Read the retained Amber interaction and sealed artifacts; never run product work."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


def text_values(output):
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = [{"type": "input_text", "text": output}]
    if not isinstance(output, list):
        return
    for block in output:
        if block.get("type") not in {"input_text", "text"}:
            continue
        value = block.get("text", "")
        try:
            yield json.loads(value)
        except json.JSONDecodeError:
            for line in value.splitlines():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    start = end = None
    for number, line in enumerate(args.trace.read_text().splitlines(), 1):
        row = json.loads(line)
        payload = row.get("payload", {})
        rows.append((number, row, payload))
        if row.get("type") != "response_item":
            continue
        if payload.get("type") == "message" and payload.get("role") == "user":
            message = "\n".join(x.get("text", "") for x in payload["content"])
            if "Amber" in message and "每道菜" in message and start is None:
                start = number
            elif start is not None:
                end = number
                break
    if start is None or end is None:
        raise ValueError("The complete Amber interaction was not found.")

    old_groups = None
    deliveries = []
    call_sites = Counter()
    selected = [(n, r, p) for n, r, p in rows if start <= n < end]
    for number, row, payload in selected:
        if row.get("type") != "response_item":
            continue
        if payload.get("type") == "custom_tool_call":
            call_sites.update(re.findall(r"tools\.([A-Za-z0-9_]+)", payload["input"]))
        if payload.get("type") not in {"custom_tool_call_output", "function_call_output"}:
            continue
        output = payload.get("output", [])
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = []
        if isinstance(output, list):
            deliveries.extend(
                hashlib.sha256(b["image_url"].encode()).hexdigest()
                for b in output
                if b.get("type") == "input_image"
            )
        for value in text_values(payload.get("output", [])):
            if old_groups is None and isinstance(value, list):
                groups = [
                    x for x in value
                    if isinstance(x, dict)
                    and "0504-Amber晚餐" in x.get("relative_path", [])
                    and "members" in x
                ]
                if groups:
                    old_groups = groups
    if old_groups is None:
        raise ValueError("The original saved Amber groups were not found.")

    with sqlite3.connect(
        (args.workspace / "plan/work-v3.sqlite3").as_uri() + "?mode=ro", uri=True
    ) as db:
        db.execute("pragma query_only=on")
        work_rows = db.execute(
            "select work_ref, result_ref, revision, state, published_path from plan_works"
        ).fetchall()
    if len(work_rows) != 1:
        raise ValueError("This session audit expects exactly one retained Work.")
    work_ref, result_ref, revision, state, published_path = work_rows[0]
    frozen_path = args.workspace / "plan" / published_path
    frozen = json.loads(frozen_path.read_bytes())
    plan = frozen["sealed_content"]

    with sqlite3.connect(
        (args.workspace / "precheck/work.sqlite3").as_uri() + "?mode=ro", uri=True
    ) as db:
        db.execute("pragma query_only=on")
        runs = db.execute(
            "select run_ref, prior_result_ref, state, created_at from precheck_runs"
        ).fetchall()
        result_row = db.execute(
            "select relative_path, digest_algorithm, digest from sealed_results where result_ref=?",
            (result_ref,),
        ).fetchone()
    if result_row is None:
        raise ValueError("The Work's Result is not retained.")
    result_path = args.workspace / "precheck" / result_row[0]
    result_bytes = result_path.read_bytes()
    digest = hashlib.new(result_row[1], result_bytes).hexdigest()
    if digest != result_row[2]:
        raise ValueError("The sealed Result does not match its recorded digest.")
    result = json.loads(result_bytes)
    relations = defaultdict(set)
    derivations = defaultdict(list)
    conditions = {}
    for relation in result["relationships"]:
        origin, kind = relation["origin"], relation["relation"]
        target = relation["member"]["target"]
        if isinstance(target, dict):
            target = target["ref"]
        relations[(origin, kind)].add(target)
        if kind == "derived_from":
            derivations[origin].append((relation["target_kind"], target))
        if kind == "accounts_for":
            conditions[target] = relation["member"]["condition"]

    def resolve(selector):
        if selector["kind"] == "precheck_relation":
            if selector["direction"] != "outbound":
                raise ValueError("Unexpected relation direction.")
            return relations[(selector["origin"], selector["relation"])]
        if selector["kind"] == "union":
            return set().union(*(resolve(s) for s in selector["sets"]))
        if selector["kind"] == "explicit":
            return set(selector["source_item_refs"])
        if selector["kind"] == "difference":
            return resolve(selector["base"]) - resolve(selector["subtract"])
        raise ValueError(f"Unsupported selector: {selector['kind']}")

    def origins(selector):
        if selector["kind"] == "precheck_relation":
            return {selector["origin"]}
        if selector["kind"] == "union":
            return set().union(*(origins(s) for s in selector["sets"]))
        raise ValueError("The original groups were not unions of whole representatives.")

    def source_lineage(ref, seen=frozenset()):
        if ref in seen:
            raise ValueError("Cyclic derivation.")
        found = set()
        for kind, target in derivations[ref]:
            if kind == "source_item":
                found.add(target)
            elif kind == "evidence":
                found.update(source_lineage(target, seen | {ref}))
        return found

    visual_sources = set()
    for evidence in result["evidence"]:
        view = evidence["view"]
        access = view.get("access", {})
        locator = access.get("locator", {})
        if (
            access.get("kind") == "local_artifact"
            and locator.get("kind") == "local_file_path"
            and Path(locator["value"]).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ):
            visual_sources.update(source_lineage(view["ref"]))
    old_members = set().union(*(resolve(g["members"]) for g in old_groups))
    old_origins = set().union(*(origins(g["members"]) for g in old_groups))
    new_groups = [g for g in plan["groups"] if "0504-Amber晚餐" in g["relative_path"]]
    new_members = [resolve(g["members"]) for g in new_groups]
    source_paths = {s["view"]["ref"]: s["relative_path"] for s in result["sources"]}
    sampled_names = {
        "DSC01230.JPG", "DSC01240.JPG", "DSC01250.JPG", "DSC01260.JPG",
        "DSC01268.JPG", "DSC01275.JPG", "DSC01285.JPG", "DSC01310.JPG",
        "DSC01485.JPG", "DSC01490.JPG", "DSC01500.JPG", "DSC01509.JPG",
    }
    boundary = {ref for ref in old_members if Path(source_paths[ref]).name in sampled_names}
    print(json.dumps({
        "trace": str(args.trace),
        "trace_line_interval": [start, end - 1],
        "result_ref": result_ref,
        "result_file_sha256": digest,
        "result_digest_verified": True,
        "work_ref": work_ref,
        "final_revision": revision,
        "work_state": state,
        "frozen_plan_ref": plan["plan_ref"],
        "same_frozen_result": plan["result_ref"] == result_ref,
        "runs": runs,
        "profile": result["preparation"]["profile"],
        "call_sites_in_recorded_js": dict(call_sites),
        "image_deliveries": len(deliveries),
        "unique_image_payloads": len(set(deliveries)),
        "old_group_count": len(old_groups),
        "new_group_count": len(new_groups),
        "original_representation_sets": len(old_origins),
        "old_source_count": len(old_members),
        "new_source_count": len(set().union(*new_members)),
        "same_source_scope": old_members == set().union(*new_members),
        "duplicate_assignments": sum(map(len, new_members)) - len(set().union(*new_members)),
        "representation_sets_split_between_groups": sum(
            sum(bool(relations[(ref, "represents")] & members) for members in new_members) > 1
            for ref in old_origins
        ),
        "source_conditions": dict(Counter(conditions[ref] for ref in old_members)),
        "sources_with_prepared_visual_lineage": len(old_members & visual_sources),
        "selected_boundary_sources": len(boundary),
        "boundary_sources_with_prepared_visual_lineage": len(boundary & visual_sources),
        "groups": [
            {"name": g["relative_path"][-1], "source_count": len(members),
             "sources_with_prepared_visual_lineage": len(members & visual_sources)}
            for g, members in zip(new_groups, new_members)
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
