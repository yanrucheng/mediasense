"""Build/install smoke runner; intentionally outside the default pytest loop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
        source = root / "source"
        source.mkdir()
        environment = os.environ.copy()
        environment.update(
            {
                "UV_TOOL_DIR": str(tool_root),
                "UV_TOOL_BIN_DIR": str(bin_root),
                "MEDIASENSE_DATA_HOME": str(root / "data"),
                "MEDIASENSE_CONFIG_HOME": str(root / "config"),
            }
        )
        environment.pop("PYTHONPATH", None)
        install_command = ["uv", "tool", "install"]
        if args.offline:
            install_command.append("--offline")
        install_command.extend(
            ["--python", "3.11", "--no-python-downloads", str(wheel)]
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
        if len(tools["tools"]) != 7:
            raise AssertionError("installed Tool discovery did not return seven Tools")
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
        skills_target = root / "skills"
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
        anyio.run(_mcp_scenario, executable, root, environment)
        _run(
            ["uv", "tool", "uninstall", "mediasense"],
            environment=environment,
            cwd=root,
        )
        if executable.exists():
            raise AssertionError("uv tool uninstall left the executable in place")
    print("distribution smoke: ok")
    return 0


async def _mcp_scenario(
    executable: Path, root: Path, environment: dict[str, str]
) -> None:
    source = root / "mcp-source"
    source.mkdir()
    workspace = root / "mcp-workspace"
    parameters = StdioServerParameters(
        command=str(executable),
        args=["mcp"],
        cwd=str(root),
        env=environment,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        if initialized.server_info.name != "mediasense":
            raise AssertionError("installed MCP server identity is incorrect")
        listed = await session.list_tools()
        if len(listed.tools) != 7:
            raise AssertionError("installed MCP discovery did not return seven Tools")
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
                "dataset_ref": dataset_ref,
                "request": {
                    "action": "start",
                    "dataset_ref": dataset_ref,
                    "request_id": "request:installed-first-use",
                },
            },
        )
        if started.is_error or started.structured_content is None:
            raise AssertionError("installed MCP PreCheck start failed")
        if started.structured_content.get("outcome") != "ok" or not str(
            started.structured_content.get("run_ref", "")
        ).startswith("precheck-run:"):
            raise AssertionError(
                f"installed MCP PreCheck start was not accepted: {started.structured_content}"
            )
        status = await session.call_tool(
            "mediasense.precheck.run",
            {
                "dataset_ref": dataset_ref,
                "request": {
                    "action": "status",
                    "run_ref": "precheck-run:not-found",
                },
            },
        )
        if status.is_error or status.structured_content is None:
            raise AssertionError("installed MCP non-destructive Tool call failed")
        if status.structured_content.get("error", {}).get("code") != "run_not_found":
            raise AssertionError("installed MCP Tool returned an unexpected outcome")


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
        contracts = [name for name in names if "/_resources/contracts/" in name]
        skill_files = [name for name in names if "/_resources/skills/" in name]
    if f"Version: {expected_version}" not in metadata:
        raise AssertionError("wheel metadata version does not match pyproject.toml")
    if "mediasense = mediasense.cli:main" not in entry_points:
        raise AssertionError("wheel does not contain the mediasense entry point")
    if len(contracts) != 9 or len(skill_files) != 8:
        raise AssertionError("wheel does not contain the required contracts and Skills")


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
