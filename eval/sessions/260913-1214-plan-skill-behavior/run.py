"""Prepare isolated synthetic Plan cases and route calls through the installed MCP Host.

The preparation path authors synthetic observations before sealing a new Result.
The evaluated Agent receives only the installed Skill, user request and case.json,
and consumes media through public PreCheck Read. No live Dataset is opened.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess


SESSION = Path(__file__).resolve().parent
ALLOWED = {"mediasense.precheck.read", "mediasense.plan.work"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def environment(root: Path) -> dict[str, str]:
    result = dict(os.environ)
    result.pop("PYTHONPATH", None)
    result.update(
        MEDIASENSE_CONFIG_HOME=str(root / "config"),
        MEDIASENSE_DATA_HOME=str(root / "data"),
        AMAP_API_KEY="",
        GOOGLE_MAPS_API_KEY="",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return result


def prepare(root: Path, host: Path, cases_path: Path) -> None:
    from PIL import Image, ImageDraw
    from mediasense.dataset_reference import dataset_id_from_ref
    from mediasense.precheck import (
        AccountingStore,
        ImageRenditionProducer,
        PrecheckReadTool,
        ResultEvidence,
        ResultRelationship,
        ResultStore,
    )
    from mediasense.runtime.host import RuntimeHost
    import mediasense

    package = Path(mediasense.__file__).resolve()
    if "site-packages" not in package.parts:
        raise RuntimeError(f"Use the isolated installation's Python: {package}")
    root.mkdir(parents=True, exist_ok=False)
    cases = json.loads(cases_path.read_text())["cases"]
    by_id = {case["id"]: case for case in cases}
    for raw in cases:
        case = deepcopy(raw)
        if "copy_items_from" in case:
            original = by_id[case["copy_items_from"]]
            case.update({k: deepcopy(original[k]) for k in ("items", "representations")})
        case_root = root / case["id"]
        source = case_root / "source"
        workspace = case_root / "dataset"
        source.mkdir(parents=True)
        os.environ.update(environment(case_root))
        for item in case["items"]:
            path = source / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".jpg":
                picture = Image.new("RGB", (1000, 400), "#ece4d7")
                draw = ImageDraw.Draw(picture)
                draw.text((35, 25), "SYNTHETIC EVIDENCE CARD / " + item["id"], fill="black", font_size=25)
                for index, line in enumerate(item["card"]):
                    draw.text((35, 95 + 45 * index), line, fill="black", font_size=24)
                picture.save(path)
            else:
                path.write_text(item.get("content", "Synthetic video source payload; see the explicitly authored sample Evidence."))
        opened = RuntimeHost().open_dataset(str(source), str(workspace))
        if opened.get("outcome") != "ok":
            raise RuntimeError(opened)
        dataset_ref = opened["dataset_ref"]
        database = workspace / "precheck/work.sqlite3"
        accounting = AccountingStore(database)
        run_id = accounting.start_or_resume_run(dataset_id_from_ref(dataset_ref), source)
        accounting.process_run(run_id)
        producer = ImageRenditionProducer(database)
        works = [
            producer.produce(run_id, Path(item["path"])).work.work_id
            for item in case["items"]
            if Path(item["path"]).suffix.lower() == ".jpg"
        ]
        store = ResultStore(database)
        draft = store.build_minimal(run_id, works)
        specifications = {item["path"]: item for item in case["items"]}
        refs = {specifications[s.relative_path.as_posix()]["id"]: s.ref for s in draft.sources}
        evidence = list(draft.evidence)
        relationships = [r for r in draft.relationships if r.relation != "represents"]
        evidence_by_source = {
            r.target_ref: r.origin_ref
            for r in draft.relationships
            if r.relation == "derived_from" and r.target_kind == "source_item"
        }
        sources = []
        for old in draft.sources:
            item = specifications[old.relative_path.as_posix()]
            extra = [
                {"name": "capture_time", "status": "available", "value": item["time"], "basis": "Synthetic retained timestamp, not a claim about a real capture."}
                if item.get("time") else {"name": "capture_time", "status": "missing"},
                {"name": "fixture_observation", "status": "available", "value": item.get("observation", item.get("readability", "Synthetic scene card; real visual recognition is not evaluated.")), "basis": "Authored synthetic fixture."},
            ]
            observations = tuple(o for o in old.observations if o["name"] != "capture_time") + tuple(extra)
            condition = item.get("condition", "usable")
            sources.append(replace(old, condition=condition, observations=observations))
            if item.get("card") and old.ref not in evidence_by_source:
                ref = "evidence:sample-" + item["id"]
                evidence.append(ResultEvidence(
                    ref=ref,
                    access={"kind": "inline", "value": {"synthetic_sample": item["card"], "limitation": "Authored sample; source bytes are synthetic and no decoder or full-stream certification is claimed."}},
                    observations=({"name": "evidence_role", "status": "available", "value": {"role": "representative"}},),
                ))
                relationships.append(ResultRelationship(ref, "derived_from", old.ref, "source_item", basis="Synthetic single-source sample."))
                evidence_by_source[old.ref] = ref
        entry = []
        for representation in case["representations"]:
            ref = evidence_by_source[refs[representation["source"]]]
            entry.append(ref)
            for member in representation["members"]:
                qualifications = tuple(
                    {"code": code, "effect": "limits_interpretation", "message": representation["basis"]}
                    for code in representation.get("limitations", ["sampled_members_only"])
                )
                relationships.append(ResultRelationship(ref, "represents", refs[member], "source_item", basis=representation["basis"], qualifications=qualifications))
                detailed = evidence_by_source.get(refs[member])
                if detailed and detailed != ref:
                    relationships.append(ResultRelationship(ref, "expands_to", detailed, "evidence", basis="A separate sample already exists for this member."))
        draft = replace(
            draft, sources=tuple(sources), evidence=tuple(evidence),
            relationships=tuple(relationships), entry_evidence=tuple(entry),
            readiness="plan_ready", coverage="complete", dataset_name=case["dataset_name"],
            dataset_context=({"provided_by": "synthetic-user", "content": case["user_request"]},),
            qualifications=({"code": "synthetic_behavior_fixture", "effect": "limits_interpretation", "message": "Synthetic inputs for Plan reasoning and interaction; this does not certify real image recognition, video decoding, GPX validity or Apply."},),
        )
        sealed = store.seal(draft)
        reviewed = PrecheckReadTool(database).read({"action": "review", "dataset_ref": dataset_ref, "result_ref": sealed.result_ref})
        if "error" in reviewed or reviewed["result"]["readiness"] != "plan_ready":
            raise RuntimeError(reviewed)
        file_hashes = {str(p.relative_to(source)): digest(p) for p in source.rglob("*") if p.is_file()}
        for p in source.rglob("*"):
            if p.is_file():
                p.chmod(0o444)
        skill_target = case_root / ".agents/skills"
        installed = subprocess.run([str(host), "skills", "install", "--target", str(skill_target), "--json"], env=environment(case_root), capture_output=True, text=True, check=True)
        save(case_root / "outputs/skill-install.json", json.loads(installed.stdout))
        save(case_root / "case.json", {
            "id": case["id"], "user_request": case["user_request"], "source": str(source),
            "workspace": str(workspace), "dataset_ref": dataset_ref,
            "result_ref": sealed.result_ref, "host": str(host),
            "skill": str(skill_target / "mediasense-plan/SKILL.md"),
            "synthetic": True,
        })
        save(case_root / "outputs/baseline.json", {
            "source_hashes": file_hashes, "result_path": str(sealed.path),
            "result_sha256": digest(sealed.path), "package": str(package),
            "source_refs": refs,
            "skill_hashes": {str(p.relative_to(skill_target)): digest(p) for p in skill_target.rglob("*") if p.is_file()},
        })
        (case_root / "request.md").write_text(case["user_request"] + "\n")
        print(case_root)


def upgrade(root: Path, host: Path) -> None:
    """Upgrade only isolated evaluation Skills; preserve old receipts for comparison."""
    for file in sorted(root.glob("*/case.json")):
        case_root = file.parent
        case = json.loads(file.read_text())
        target = case_root / ".agents/skills"
        upgraded = subprocess.run(
            [str(host), "skills", "upgrade", "--target", str(target), "--json"],
            env=environment(case_root), capture_output=True, text=True, check=True,
        )
        save(case_root / "outputs/skill-upgrade.json", json.loads(upgraded.stdout))
        case["host"] = str(host)
        save(file, case)
        save(case_root / "outputs/upgraded-skill-hashes.json", {
            str(p.relative_to(target)): digest(p) for p in target.rglob("*") if p.is_file()
        })


async def tool(case_root: Path, name: str | None, request_path: Path | None, discovery: bool = False) -> object:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    case = json.loads((case_root / "case.json").read_text())
    request = json.loads(request_path.read_text()) if request_path else {}
    if not discovery:
        if name not in ALLOWED or request.get("action") == "seal":
            raise ValueError("This isolated behavior evaluation permits Read and unsealed Plan Work only.")
        if "authority" in request:
            raise ValueError("Synthetic interaction supplies no trusted Human authority.")
    params = StdioServerParameters(command=case["host"], args=["mcp"], cwd=str(case_root), env=environment(case_root))
    async with stdio_client(params) as (incoming, outgoing), ClientSession(incoming, outgoing) as session:
        initialization = await session.initialize()
        listing = await session.list_tools()
        if discovery:
            result = {"server": initialization.model_dump(mode="json"), "tools": [t.model_dump(mode="json") for t in listing.tools]}
        else:
            opened = await session.call_tool("mediasense.dataset.open", {"source_root": case["source"], "workspace": case["workspace"]})
            if opened.structured_content.get("dataset_ref") != case["dataset_ref"]:
                raise RuntimeError(opened)
            args = {"dataset_ref": case["dataset_ref"], "request": request} if name == "mediasense.plan.work" else {**request, "dataset_ref": case["dataset_ref"]}
            response = await session.call_tool(name, args)
            result = response.structured_content
            if result is None:
                raise RuntimeError(response)
        record = {"tool": "discovery" if discovery else name, "request": request, "response": result}
        with (case_root / "outputs/mcp.jsonl").open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return result


def verify(root: Path) -> dict:
    cases = []
    for file in sorted(root.glob("*/case.json")):
        case_root = file.parent
        case = json.loads(file.read_text())
        baseline = json.loads((case_root / "outputs/baseline.json").read_text())
        now = {str(p.relative_to(case["source"])): digest(p) for p in Path(case["source"]).rglob("*") if p.is_file()}
        if now != baseline["source_hashes"] or digest(Path(baseline["result_path"])) != baseline["result_sha256"]:
            raise AssertionError("source or Result changed: " + case["id"])
        trace_path = case_root / "outputs/mcp.jsonl"
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
        candidates = []
        for index, record in enumerate(trace):
            request = record["request"]
            if request.get("candidate_content"):
                candidates.append({"trace_index": index, "candidate": request["candidate_content"], "response": record["response"]})
        cases.append({"case": case["id"], "source_unchanged": True, "result_unchanged": True, "tool_calls": len(trace), "candidate_submissions": candidates, "trace_sha256": digest(trace_path) if trace_path.exists() else None})
    return {"cases": cases, "limitations": "Mechanical capture and immutability verification only; behavior conclusions require review of the actual dialogue, evidence use and dispositions."}


def summarize(roots: list[Path], release: Path, session_directory: Path) -> dict:
    """Retain bounded proof of actual installed reads, calls and unchanged artifacts."""
    cases = []
    skills = {
        "final": release / "source/src/mediasense/_resources/skills/mediasense-plan/SKILL.md",
        "first": release.parent / "source/src/mediasense/_resources/skills/mediasense-plan/SKILL.md",
    }
    profile = release / "source/docs/spec/contract/default-organization-profile/index.md"
    agent_sessions = []
    for path in sorted(session_directory.glob("*.jsonl")):
        with path.open() as stream:
            first = json.loads(stream.readline())
        meta = first.get("payload", {})
        agent = meta.get("agent_path", "")
        if not agent.startswith(("/root/plan_case_", "/root/plan_final_")):
            continue
        raw = path.read_bytes()
        records = [json.loads(line) for line in raw.splitlines()]
        reads = []
        models = set()
        image_events = []
        for line_number, record in enumerate(records, 1):
            payload = record.get("payload", {})
            if record.get("type") == "turn_context":
                models.add((payload.get("model"), payload.get("effort")))
            item = payload.get("item", {})
            if item.get("type") == "CommandExecution":
                output = item.get("stdout", "")
                for label, expected in (*skills.items(), ("profile", profile)):
                    if expected.read_text() in output:
                        reads.append({"line": line_number, "resource": label, "sha256": digest(expected)})
            if item.get("type") == "ImageView":
                image_events.append({"line": line_number, "path": item.get("path")})
        if reads:
            agent_sessions.append({
                "agent": agent, "path": str(path), "snapshot_lines": len(records),
                "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
                "models": [{"model": model, "effort": effort} for model, effort in sorted(models)],
                "complete_resource_reads": reads,
                "image_views": image_events,
            })
    from collections import Counter

    for root in roots:
        verify(root)
        for file in sorted(root.glob("*/case.json")):
            folder = file.parent
            trace_file = folder / "outputs/mcp.jsonl"
            if not trace_file.exists():
                continue
            trace = [json.loads(line) for line in trace_file.read_text().splitlines()]
            baseline = json.loads((folder / "outputs/baseline.json").read_text())
            ref_ids = {value: key for key, value in baseline["source_refs"].items()}
            identities = []
            latest = None
            for record in trace:
                response = record["response"]
                identity = response.get("candidate_content_identity")
                if identity and identity not in identities:
                    identities.append(identity)
                if record["request"].get("action") == "inspect" and identity:
                    latest = response
            candidate = latest["sections"]["content"]["value"] if latest else None
            installed = folder / ".agents/skills/mediasense-plan"
            cases.append({
                "case": file.parent.name, "root": str(folder),
                "calls": dict(sorted(Counter(record["tool"] + ":" + record["request"].get("action", "list") for record in trace).items())),
                "errors": [r["response"].get("error") for r in trace if "error" in r["response"]],
                "candidate_identities": identities,
                "work_ref": latest.get("work_ref") if latest else None,
                "revision": latest.get("revision") if latest else None,
                "validation": latest["sections"].get("validation") if latest else None,
                "groups": [{"path": g["relative_path"], "members": [ref_ids.get(ref, ref) for ref in g["members"].get("source_item_refs", [])]} for g in candidate["groups"]] if candidate else [],
                "other_outcomes": [{"outcome": o["outcome"], "members": [ref_ids.get(ref, ref) for ref in o["members"].get("source_item_refs", [])], "reason": o.get("reason")} for o in candidate["other_outcomes"]] if candidate else [],
                "decision_note_count": len(candidate.get("decision_notes", [])) if candidate else 0,
                "trace_sha256": digest(trace_file),
                "skill_sha256": digest(installed / "SKILL.md"),
                "profile_sha256": digest(installed / "references/default-organization-profile.md"),
                "source_unchanged": True, "result_unchanged": True,
                "report": str(folder / "agent/result.md"),
                "forbidden_calls": sum(r["tool"] not in ALLOWED | {"discovery"} or r["request"].get("action") == "seal" for r in trace),
            })
    wheel = next((release / "wheel").glob("*.whl"))
    return {
        "release": str(release), "wheel": str(wheel), "wheel_sha256": digest(wheel),
        "source_commit": json.loads((release / "source-identity.json").read_text())["commit"],
        "skill_sha256": digest(skills["final"]), "profile_sha256": digest(profile),
        "config_sha256": digest(SESSION / "config.json"), "runner_sha256": digest(Path(__file__)),
        "agent_sessions": agent_sessions, "cases": cases,
        "daily_installation_switched": False, "extra_geo_provider_calls": 0,
        "agent_model_use": "occurred; token/egress/cost not independently measured",
        "limits": "Synthetic independent execution and actual installed MCP receipts; no population success rate, causal improvement, real media recognition or human confirmation claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    setup = actions.add_parser("prepare")
    setup.add_argument("--output", type=Path, required=True)
    setup.add_argument("--host", type=Path, required=True)
    setup.add_argument("--config", type=Path, default=SESSION / "config.json")
    refresh = actions.add_parser("upgrade")
    refresh.add_argument("--output", type=Path, required=True)
    refresh.add_argument("--host", type=Path, required=True)
    call = actions.add_parser("tool")
    call.add_argument("--case", type=Path, required=True)
    call.add_argument("--name")
    call.add_argument("--request", type=Path)
    call.add_argument("--discover", action="store_true")
    check = actions.add_parser("verify")
    check.add_argument("--output", type=Path, required=True)
    summary = actions.add_parser("summary")
    summary.add_argument("--root", type=Path, action="append", required=True)
    summary.add_argument("--release", type=Path, required=True)
    summary.add_argument("--sessions", type=Path, required=True)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.output.resolve(), args.host.resolve(), args.config.resolve())
    elif args.action == "tool":
        import anyio
        print(json.dumps(anyio.run(tool, args.case.resolve(), args.name, args.request, args.discover), ensure_ascii=False))
    elif args.action == "upgrade":
        upgrade(args.output.resolve(), args.host.resolve())
    elif args.action == "summary":
        result = summarize([p.resolve() for p in args.root], args.release.resolve(), args.sessions.resolve())
        save(args.output.resolve(), result)
        print(json.dumps({"cases": len(result["cases"]), "agent_sessions": len(result["agent_sessions"]), "output": str(args.output)}, ensure_ascii=False))
    else:
        print(json.dumps(verify(args.output.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
