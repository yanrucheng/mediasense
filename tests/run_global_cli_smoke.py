"""Probe one exact installed MediaSense executable; outside the pytest suite."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "mediasense.dataset.open",
    "mediasense.precheck.run",
    "mediasense.precheck.read",
    "mediasense.plan.work",
    "mediasense.apply.run",
    "mediasense.apply.read",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()

    executable = args.executable.resolve(strict=True)
    repository = Path(__file__).resolve().parents[1]
    if not executable.is_absolute():
        raise AssertionError("the installed executable path must be absolute")
    if executable.is_relative_to(repository / ".venv"):
        raise AssertionError("the installed-runtime probe must not use .venv")

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("VIRTUAL_ENV", None)
    version = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    ).stdout.strip()
    if version != f"mediasense {args.expected_version}":
        raise AssertionError(f"unexpected installed version: {version}")

    anyio.run(_probe_mcp, executable, args.expected_version, environment)
    print(f"global CLI smoke: ok ({executable}, {args.expected_version})")
    return 0


async def _probe_mcp(
    executable: Path, expected_version: str, environment: dict[str, str]
) -> None:
    with tempfile.TemporaryDirectory(prefix="mediasense-global-cli-smoke-") as raw:
        root = Path(raw)
        source = root / "source"
        workspace = root / "workspace"
        source.mkdir()
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
            if initialized.server_info.version != expected_version:
                raise AssertionError(
                    "installed MCP version does not match the expected release"
                )
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            if names != EXPECTED_TOOLS:
                raise AssertionError(f"unexpected installed Tool set: {sorted(names)}")

            opened = await session.call_tool(
                "mediasense.dataset.open",
                {"source_root": str(source), "workspace": str(workspace)},
            )
            if opened.is_error or opened.structured_content is None:
                raise AssertionError("installed Dataset Open failed")
            dataset_ref = opened.structured_content["dataset_ref"]
            started = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "start",
                        "dataset_ref": dataset_ref,
                        "request_id": "request:installed-global-first-use",
                    },
                },
            )
            if started.is_error or started.structured_content is None:
                raise AssertionError("installed PreCheck Start failed")
            if started.structured_content.get("outcome") != "ok" or not str(
                started.structured_content.get("run_ref", "")
            ).startswith("precheck-run:"):
                raise AssertionError(
                    "installed PreCheck Start did not return a Run: "
                    f"{started.structured_content}"
                )


if __name__ == "__main__":
    raise SystemExit(main())
