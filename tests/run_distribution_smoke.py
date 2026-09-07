"""Build/install smoke runner; intentionally outside the default pytest loop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "mediasense.dataset.open",
    "mediasense.precheck.run",
    "mediasense.precheck.read",
    "mediasense.plan.work",
    "mediasense.geo.query",
    "mediasense.apply.run",
    "mediasense.apply.read",
}
EXPECTED_CONTRACT_FILES = {
    "apply-read.tool.json",
    "apply-receipt.schema.json",
    "apply-run.tool.json",
    "dataset-open.tool.json",
    "frozen-plan.schema.json",
    "geo-query.tool.json",
    "plan-work.tool.json",
    "precheck-read.tool.json",
    "precheck-run.tool.json",
}
EXPECTED_SKILL_FILES = {
    "mediasense/SKILL.md",
    "mediasense/agents/openai.yaml",
    "mediasense-apply/SKILL.md",
    "mediasense-apply/agents/openai.yaml",
    "mediasense-plan/SKILL.md",
    "mediasense-plan/agents/openai.yaml",
    "mediasense-plan/references/organization-profiles.md",
    "mediasense-precheck/SKILL.md",
    "mediasense-precheck/agents/openai.yaml",
    "mediasense-precheck/references/precheck-read.tool.json",
    "mediasense-precheck/references/precheck-run.tool.json",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Require every dependency to be available in the local uv cache.",
    )
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    expected_version = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )["project"]["version"]
    _verify_wheel(wheel, expected_version)
    with tempfile.TemporaryDirectory(prefix="mediasense-clean-install-") as temporary:
        root = Path(temporary)
        tool_root = root / "tools"
        bin_root = root / "bin"
        home = root / "home"
        honeycomb = root / "honeycomb"
        source = root / "source"
        home.mkdir()
        source.mkdir()
        environment = os.environ.copy()
        environment.setdefault(
            "UV_CACHE_DIR",
            subprocess.check_output(["uv", "cache", "dir"], text=True).strip(),
        )
        environment.update(
            {
                "UV_TOOL_DIR": str(tool_root),
                "UV_TOOL_BIN_DIR": str(bin_root),
                "HOME": str(home),
                "MEDIASENSE_DATA_HOME": str(root / "data"),
                "MEDIASENSE_CONFIG_HOME": str(root / "config"),
            }
        )
        environment.pop("PYTHONPATH", None)
        install_command = ["uv", "tool", "install"]
        if args.offline:
            install_command.append("--offline")
        install_command.extend(
            [
                "--python",
                str(Path(sys.executable).resolve()),
                "--no-python-downloads",
                str(wheel),
            ]
        )
        _run(
            install_command,
            environment=environment,
            cwd=root,
        )
        executable = bin_root / "mediasense"
        version = _run(
            [str(executable), "--version"], environment=environment, cwd=root
        )
        if expected_version not in version:
            raise AssertionError(f"unexpected installed version: {version}")
        _assert_no_agent_configuration(home)
        doctor = _json_run(
            [str(executable), "doctor", "--json"],
            environment=environment,
            cwd=root,
        )
        if doctor["status"] != "ok":
            raise AssertionError(f"installed doctor failed: {doctor}")
        tools = _json_run(
            [str(executable), "tools", "list", "--json"],
            environment=environment,
            cwd=root,
        )
        tool_names = {str(tool["name"]) for tool in tools["tools"]}
        if tool_names != EXPECTED_TOOLS:
            raise AssertionError(
                f"installed Tool discovery mismatch: {sorted(tool_names)}"
            )
        first = _json_run(
            [str(executable), "dataset", "open", str(source), "--json"],
            environment=environment,
            cwd=root,
        )
        second = _json_run(
            [str(executable), "dataset", "open", str(source), "--json"],
            environment=environment,
            cwd=root,
        )
        if first["dataset_ref"] != second["dataset_ref"] or second["created"]:
            raise AssertionError("installed Dataset open is not idempotent")
        skills_target = honeycomb / ".agents" / "skills"
        _json_run(
            [
                str(executable),
                "skills",
                "install",
                "--target",
                str(skills_target),
                "--json",
            ],
            environment=environment,
            cwd=root,
        )
        if not all(
            (skills_target / name / "SKILL.md").is_file()
            for name in (
                "mediasense",
                "mediasense-precheck",
                "mediasense-plan",
                "mediasense-apply",
            )
        ):
            raise AssertionError("Skills were not installed under the explicit target")
        _assert_no_agent_configuration(home)
        if (Path(first["workspace"]) / ".agents").exists() or (
            Path(first["workspace"]) / ".codex"
        ).exists():
            raise AssertionError("Skill installation was coupled to Dataset state")
        result_ref = _seed_plan_ready_result(
            executable,
            Path(first["workspace"]),
            source,
            str(first["dataset_ref"]),
            environment,
            root,
        )
        anyio.run(
            _mcp_scenario,
            executable,
            source,
            Path(first["workspace"]),
            environment,
            result_ref,
            expected_version,
        )
        _run(
            ["uv", "tool", "uninstall", "mediasense"],
            environment=environment,
            cwd=root,
        )
        if executable.exists():
            raise AssertionError("uv tool uninstall left the executable in place")
    print("distribution smoke: ok")
    return 0


def _assert_no_agent_configuration(home: Path) -> None:
    if (home / ".codex" / "config.toml").exists():
        raise AssertionError("CLI installation wrote user-level Codex configuration")
    if (home / ".codex" / "skills").exists():
        raise AssertionError("CLI installation wrote user-level Codex Skills")
    if (home / ".agents" / "skills").exists():
        raise AssertionError("CLI installation wrote user-level Agent Skills")


def _seed_plan_ready_result(
    executable: Path,
    workspace: Path,
    source: Path,
    dataset_ref: str,
    environment: dict[str, str],
    cwd: Path,
) -> str:
    script = """
from pathlib import Path
from PIL import Image
from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.precheck import AccountingStore, ImageRenditionProducer, ResultStore

workspace = Path(__import__('sys').argv[1])
source = Path(__import__('sys').argv[2])
dataset_ref = __import__('sys').argv[3]
media = source / 'original.jpg'
Image.new('RGB', (80, 40), 'purple').save(media)
database = workspace / 'precheck' / 'work.sqlite3'
accounting = AccountingStore(database)
run_id = accounting.start_or_resume_run(dataset_id_from_ref(dataset_ref), source)
accounting.process_run(run_id)
rendition = ImageRenditionProducer(database).produce(run_id, Path('original.jpg'))
store = ResultStore(database)
print(store.seal(store.build_minimal(run_id, [rendition.work.work_id])).result_ref)
"""
    return _run(
        [
            str(executable.resolve().parent / "python"),
            "-c",
            script,
            str(workspace),
            str(source),
            dataset_ref,
        ],
        environment=environment,
        cwd=cwd,
    ).strip()


async def _mcp_scenario(
    executable: Path,
    source: Path,
    workspace: Path,
    environment: dict[str, str],
    result_ref: str,
    expected_version: str,
) -> None:
    parameters = StdioServerParameters(
        command=str(executable),
        args=["mcp"],
        cwd=str(source.parent),
        env=environment,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        if initialized.server_info.name != "mediasense":
            raise AssertionError("installed MCP server identity is incorrect")
        if initialized.server_info.version != expected_version:
            raise AssertionError(
                "installed MCP server version is not the installed CLI version"
            )
        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        if tool_names != EXPECTED_TOOLS:
            raise AssertionError(
                f"installed MCP discovery mismatch: {sorted(tool_names)}"
            )
        for tool in listed.tools:
            metadata = tool.meta or {}
            if not str(metadata.get("contract_id", "")).startswith("urn:mediasense:"):
                raise AssertionError(
                    f"installed MCP Tool lacks contract identity: {tool.name}"
                )
            if not str(metadata.get("contract_digest", "")).startswith("sha256:"):
                raise AssertionError(
                    f"installed MCP Tool lacks contract digest: {tool.name}"
                )
        opened = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        if opened.is_error or opened.structured_content is None:
            raise AssertionError("installed MCP Dataset open failed")
        dataset_ref = opened.structured_content["dataset_ref"]
        started = await session.call_tool(
            "mediasense.precheck.run",
            {
                **{
                    "action": "start",
                    "dataset_ref": dataset_ref,
                    "request_id": "request:installed-first-use",
                },
                "dataset_ref": dataset_ref,
            },
        )
        if started.is_error or started.structured_content is None:
            raise AssertionError("installed MCP PreCheck start failed")
        if "error" in started.structured_content or not str(
            started.structured_content.get("run_ref", "")
        ).startswith("precheck-run:"):
            raise AssertionError(
                f"installed MCP PreCheck start was not accepted: {started.structured_content}"
            )
        status = await session.call_tool(
            "mediasense.precheck.run",
            {
                **{
                    "dataset_ref": "dataset:dataset-a",
                    "action": "status",
                    "run_ref": "precheck-run:not-found",
                },
                "dataset_ref": dataset_ref,
            },
        )
        if not status.is_error:
            raise AssertionError("installed MCP query failure did not set isError")
        if (
            json.loads(status.content[0].text).get("error", {}).get("code")
            != "run_not_found"
        ):
            raise AssertionError("installed MCP Tool returned an unexpected outcome")

        created = await session.call_tool(
            "mediasense.plan.work",
            {
                "dataset_ref": dataset_ref,
                "request": {
                    "action": "create",
                    "result_ref": result_ref,
                    "request_id": "request:installed-plan-create",
                },
            },
        )
        if created.is_error or created.structured_content is None:
            raise AssertionError("installed MCP Plan create failed")
        if created.structured_content.get("outcome") != "ok" or not str(
            created.structured_content.get("work_ref", "")
        ).startswith("plan-work:"):
            raise AssertionError(
                f"installed MCP Plan create returned an unexpected outcome: "
                f"{created.structured_content}"
            )


def _verify_wheel(wheel: Path, expected_version: str) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        entry_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        metadata = archive.read(metadata_name).decode()
        entry_points = archive.read(entry_name).decode()
        contracts = {
            name.split("/_resources/contracts/", maxsplit=1)[1]
            for name in names
            if "/_resources/contracts/" in name
        }
        skill_files = {
            name.split("/_resources/skills/", maxsplit=1)[1]
            for name in names
            if "/_resources/skills/" in name
        }
    if f"Version: {expected_version}" not in metadata:
        raise AssertionError("wheel metadata version does not match pyproject.toml")
    if "mediasense = mediasense.cli:main" not in entry_points:
        raise AssertionError("wheel does not contain the mediasense entry point")
    if contracts != EXPECTED_CONTRACT_FILES:
        raise AssertionError(f"wheel contract resources mismatch: {sorted(contracts)}")
    if skill_files != EXPECTED_SKILL_FILES:
        raise AssertionError(f"wheel Skill resources mismatch: {sorted(skill_files)}")


def _run(command: list[str], *, environment: dict[str, str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        cwd=cwd,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def _json_run(
    command: list[str], *, environment: dict[str, str], cwd: Path
) -> dict[str, object]:
    value = json.loads(_run(command, environment=environment, cwd=cwd))
    if not isinstance(value, dict):
        raise TypeError(f"command did not return a JSON object: {command!r}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
