"""Human-facing MediaSense command line control surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .runtime.composition import HostRequestError, tool_descriptors
from .runtime.dataset import DatasetOpenError, DatasetResolver, inspect_workspace
from .runtime.doctor import diagnose
from .runtime.host import RuntimeHost
from .runtime.mcp_host import run_stdio
from .runtime.resources import skill_roots
from .runtime.skills import SkillInstallError, install_skills, upgrade_skills
from .runtime.versioning import application_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediasense",
        description="Prepare, plan, and safely apply organization for local media.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {application_version()}"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    version_parser = subcommands.add_parser(
        "version", help="Show the installed version."
    )
    version_parser.add_argument("--json", action="store_true")

    doctor_parser = subcommands.add_parser(
        "doctor",
        help="Check installation and optional capabilities without changing them.",
    )
    doctor_parser.add_argument("--json", action="store_true")

    dataset_parser = subcommands.add_parser("dataset", help="Open Dataset state.")
    dataset_commands = dataset_parser.add_subparsers(
        dest="dataset_command", required=True
    )
    open_parser = dataset_commands.add_parser(
        "open", help="Find or create the Dataset workspace for a source path."
    )
    open_parser.add_argument("source_root")
    open_parser.add_argument("--workspace")
    open_parser.add_argument("--json", action="store_true")
    inspect_parser = dataset_commands.add_parser(
        "inspect", help="Inspect an existing Dataset workspace without changing it."
    )
    inspect_parser.add_argument("workspace")
    inspect_parser.add_argument("--json", action="store_true")

    tools_parser = subcommands.add_parser("tools", help="Inspect or call hosted Tools.")
    tool_commands = tools_parser.add_subparsers(dest="tools_command", required=True)
    list_parser = tool_commands.add_parser("list", help="List hosted Tool contracts.")
    list_parser.add_argument("--json", action="store_true")
    show_parser = tool_commands.add_parser(
        "show", help="Show one hosted Tool contract."
    )
    show_parser.add_argument("name")
    show_parser.add_argument("--json", action="store_true")
    call_parser = tool_commands.add_parser(
        "call", help="Invoke one Tool through the same local composition as MCP."
    )
    call_parser.add_argument("name")
    call_parser.add_argument("--source", required=True)
    call_parser.add_argument("--workspace")
    call_parser.add_argument("--request", required=True)
    call_parser.add_argument("--authority")
    call_parser.add_argument("--json", action="store_true")

    skills_parser = subcommands.add_parser(
        "skills", help="Locate or explicitly install the packaged Agent Skills."
    )
    skill_commands = skills_parser.add_subparsers(dest="skills_command", required=True)
    path_parser = skill_commands.add_parser(
        "path", help="Show the packaged Skill directories."
    )
    path_parser.add_argument("--json", action="store_true")
    install_parser = skill_commands.add_parser(
        "install",
        help="Install Skills only under an explicit target, without overwriting.",
    )
    install_parser.add_argument("--target", required=True)
    install_parser.add_argument("--json", action="store_true")
    upgrade_parser = skill_commands.add_parser(
        "upgrade",
        help="Transactionally replace only the packaged MediaSense Skills.",
    )
    upgrade_parser.add_argument("--target", required=True)
    upgrade_parser.add_argument("--json", action="store_true")

    subcommands.add_parser(
        "mcp", help="Run the session-scoped local MCP server over stdio."
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "version":
        value = {"version": application_version()}
        _emit(value, json_output=args.json, human=f"MediaSense {value['version']}")
        return 0
    if args.command == "doctor":
        value = diagnose()
        _emit(value, json_output=args.json, human=_doctor_text(value))
        return 1 if value["status"] == "error" else 0
    if args.command == "dataset":
        if args.dataset_command == "inspect":
            try:
                value = inspect_workspace(Path(args.workspace))
            except DatasetOpenError as error:
                value = {
                    "outcome": "error",
                    "error": {"code": error.code, "message": str(error)},
                    **({} if error.path is None else {"path": str(error.path)}),
                }
            human = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            host = RuntimeHost(DatasetResolver())
            value = host.open_dataset(args.source_root, args.workspace)
            human = _dataset_text(value)
        _emit(value, json_output=args.json, human=human)
        return 0 if value.get("outcome") == "ok" else 2
    if args.command == "tools" and args.tools_command == "list":
        value = {"tools": list(RuntimeHost.tools())}
        _emit(value, json_output=args.json, human=_tools_text(value))
        return 0
    if args.command == "tools" and args.tools_command == "show":
        descriptor = next(
            (item for item in tool_descriptors() if item.name == args.name), None
        )
        if descriptor is None:
            value = {
                "outcome": "error",
                "error": {
                    "code": "tool_not_found",
                    "message": f"Unknown MediaSense Tool: {args.name}",
                },
            }
            exit_code = 2
        else:
            value = {
                **descriptor.to_value(),
                "input_schema": descriptor.input_schema,
                "output_schema": descriptor.output_schema,
            }
            exit_code = 0
        _emit(
            value,
            json_output=args.json,
            human=json.dumps(value, ensure_ascii=False, indent=2),
        )
        return exit_code
    if args.command == "tools" and args.tools_command == "call":
        return _call_tool(args)
    if args.command == "skills" and args.skills_command == "path":
        paths = [str(path) for path in skill_roots()]
        value = {"skills": paths}
        _emit(value, json_output=args.json, human="\n".join(paths))
        return 0
    if args.command == "skills" and args.skills_command in {"install", "upgrade"}:
        try:
            operation = (
                install_skills if args.skills_command == "install" else upgrade_skills
            )
            value = operation(Path(args.target))
        except (OSError, SkillInstallError) as error:
            value = {
                "outcome": "error",
                "error": {"code": "skill_install_failed", "message": str(error)},
            }
        _emit(
            value,
            json_output=args.json,
            human=json.dumps(value, ensure_ascii=False, indent=2),
        )
        return 0 if value.get("outcome") == "ok" else 2
    if args.command == "mcp":
        run_stdio()
        return 0
    raise AssertionError("unreachable command")


def main() -> None:
    raise SystemExit(run())


def _call_tool(args: argparse.Namespace) -> int:
    try:
        request = _json_argument(args.request)
        authority = None if args.authority is None else _json_argument(args.authority)
        host = RuntimeHost()
        opened = host.open_dataset(args.source, args.workspace)
        if opened.get("outcome") != "ok":
            value = opened
            human = _dataset_text(opened)
            outcome = opened.get("outcome")
        else:
            result = host.call_tool(
                args.name,
                dataset_ref=str(opened["dataset_ref"]),
                request=request,
                authority=authority,
            )
            value = {"dataset": opened, "result": result}
            human = (
                _dataset_text(opened)
                + "\n\nTool result\n"
                + json.dumps(result, ensure_ascii=False, indent=2)
            )
            outcome = result.get("outcome")
    except (HostRequestError, OSError, ValueError, json.JSONDecodeError) as error:
        value = {
            "outcome": "error",
            "error": {"code": "invalid_invocation", "message": str(error)},
        }
        human = json.dumps(value, ensure_ascii=False, indent=2)
        outcome = value.get("outcome")
    _emit(value, json_output=args.json, human=human)
    return 0 if outcome in {"ok", "accepted"} else 2


def _json_argument(value: str) -> dict[str, Any]:
    if value.startswith("@"):
        text = Path(value[1:]).read_text(encoding="utf-8")
    else:
        text = value
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("JSON input must be an object")
    return parsed


def _emit(value: object, *, json_output: bool, human: str) -> None:
    print(
        json.dumps(value, ensure_ascii=False, sort_keys=True) if json_output else human
    )


def _dataset_text(value: dict[str, object]) -> str:
    if value.get("outcome") != "ok":
        error = value.get("error", {})
        return f"Dataset open failed: {error}"
    config = value.get("configuration", {})
    lines = [
        "MediaSense Dataset",
        f"  source: {value['source_root']}",
        f"  dataset: {value['dataset_ref']}",
        f"  workspace: {value['workspace']}",
        f"  selected by: {value['selection_tier']}",
        f"  created: {'yes' if value['created'] else 'no'}",
    ]
    if isinstance(config, dict):
        lines.append(f"  offline: {str(config.get('offline')).lower()}")
        sources = config.get("sources", [])
        lines.append(
            "  config: "
            + (", ".join(str(item) for item in sources) or "built-in defaults")
        )
    for warning in value.get("warnings", []):
        lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def _doctor_text(value: dict[str, object]) -> str:
    lines = [f"MediaSense {value['application_version']} doctor"]
    symbols = {"ok": "OK", "warning": "WARN", "error": "ERROR"}
    for check in value["checks"]:
        assert isinstance(check, dict)
        lines.append(
            f"  [{symbols[str(check['status'])]}] {check['name']}: {check['message']}"
        )
    return "\n".join(lines)


def _tools_text(value: dict[str, object]) -> str:
    lines = ["MediaSense Tools"]
    for item in value["tools"]:
        assert isinstance(item, dict)
        lines.append(f"  {item['name']} — {item['description']}")
    return "\n".join(lines)
