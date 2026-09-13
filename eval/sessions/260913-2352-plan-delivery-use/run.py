"""Capture ordinary installed MCP calls for the Plan page-use evaluation.

The existing synthetic-case producer is reused. This adapter records transport
input/output; it makes no planning decisions or presentation business data.
"""

import argparse
import importlib.util
import json
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SESSION = Path(__file__).resolve().parent
BASE_PATH = SESSION.parent / "260913-1214-plan-skill-behavior/run.py"
spec = importlib.util.spec_from_file_location("plan_case_producer", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


async def call(root, name, request_file=None):
    case = json.loads((root / "case.json").read_text())
    request = json.loads(request_file.read_text()) if request_file else None
    if name not in {"mediasense.precheck.read", "mediasense.plan.work"}:
        raise ValueError(
            "Only public Read and Plan Work are permitted in this evaluation"
        )
    authority = None
    if request and request.get("action") == "seal":
        # The evaluator supplies this only after reviewing the page and issuing
        # an explicitly recorded simulated acceptance event.
        path = root / "outputs/review-authority.json"
        if path.exists():
            authority = json.loads(path.read_text())
    parameters = StdioServerParameters(
        command=case["host"], args=["mcp"], cwd=str(root), env=base.environment(root)
    )
    async with (
        stdio_client(parameters) as (incoming, outgoing),
        ClientSession(incoming, outgoing) as session,
    ):
        initialization = await session.initialize()
        if request is None:
            listing = await session.list_tools()
            result = {
                "server": initialization.model_dump(mode="json"),
                "tools": [
                    tool.model_dump(mode="json")
                    for tool in listing.tools
                    if tool.name == name
                ],
            }
        else:
            opened = await session.call_tool(
                "mediasense.dataset.open",
                {
                    "source_root": case["source"],
                    "workspace": case["workspace"],
                },
            )
            assert opened.structured_content["dataset_ref"] == case["dataset_ref"]
            arguments = (
                {"dataset_ref": case["dataset_ref"], "request": request}
                if name == "mediasense.plan.work"
                else {**request, "dataset_ref": case["dataset_ref"]}
            )
            if authority is not None:
                arguments["authority"] = authority
            reply = await session.call_tool(name, arguments)
            assert reply.content == [] and reply.structured_content is not None
            result = reply.structured_content
        with (root / "outputs/mcp.jsonl").open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "tool": name,
                        "request": request,
                        "authority": authority,
                        "response": result,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return result


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--host", type=Path, required=True)
    invoke = sub.add_parser("tool")
    invoke.add_argument("case", type=Path)
    invoke.add_argument("name")
    invoke.add_argument("request", type=Path, nargs="?")
    args = parser.parse_args()
    if args.action == "prepare":
        base.prepare(
            args.output.resolve(), args.host.resolve(), SESSION / "config.json"
        )
    else:
        print(
            json.dumps(
                anyio.run(call, args.case.resolve(), args.name, args.request),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
