"""Installed CLI/MCP Geo recovery via production adapters and loopback TLS proxies.

No fake Geo provider is injected. Proxies terminate all map HTTPS locally and never
forward traffic. Run with the isolated installed Python and --host from that install.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import threading
from urllib.parse import parse_qs, urlsplit

import anyio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from PIL import Image, ImageDraw


@contextmanager
def proxy(certificate, key, *, fail_lat=None):
    records = []
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)

    class Inner(BaseHTTPRequestHandler):
        def do_GET(self):
            values = parse_qs(urlsplit(self.path).query)
            if self.headers["Host"].startswith("restapi.amap.com"):
                lon, lat = map(float, values["location"][0].split(","))
                records.append(
                    {
                        "provider": "amap",
                        "operation": "resolve_place",
                        "latitude": lat,
                        "status": "success",
                    }
                )
                self.reply(
                    {
                        "status": "1",
                        "regeocode": {
                            "formatted_address": "Synthetic mainland address",
                            "addressComponent": {"country": "China"},
                            "pois": [
                                {
                                    "name": "Synthetic mainland place",
                                    "location": f"{lon},{lat}",
                                }
                            ],
                        },
                    }
                )
            else:
                lat, lon = map(float, values["latlng"][0].split(","))
                records.append(
                    {
                        "provider": "google_maps",
                        "operation": "reverse_geocode",
                        "latitude": lat,
                        "status": "success",
                    }
                )
                self.reply(
                    {
                        "status": "OK",
                        "results": [
                            {
                                "formatted_address": "Synthetic overseas address",
                                "address_components": [
                                    {
                                        "long_name": "Japan",
                                        "short_name": "JP",
                                        "types": ["country"],
                                    }
                                ],
                            }
                        ],
                    }
                )

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            center = body["locationRestriction"]["circle"]["center"]
            lat = center["latitude"]
            lost = fail_lat is not None and abs(lat - fail_lat) < 0.00001
            records.append(
                {
                    "provider": "google_maps",
                    "operation": "nearby_places",
                    "latitude": lat,
                    "status": "response_lost" if lost else "success",
                }
            )
            if lost:
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            self.reply(
                {
                    "places": [
                        {
                            "displayName": {"text": "Synthetic nearby place"},
                            "location": center,
                        }
                    ]
                }
            )

        def reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Outer(BaseHTTPRequestHandler):
        def do_CONNECT(self):
            if self.path not in {
                "maps.googleapis.com:443",
                "places.googleapis.com:443",
                "restapi.amap.com:443",
            }:
                self.send_error(403)
                return
            self.send_response(200, "Connection established")
            self.end_headers()
            self.close_connection = True
            try:
                with context.wrap_socket(self.connection, server_side=True) as secured:
                    Inner(secured, self.client_address, self.server)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Outer)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", records
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)


def media(root, points):
    root.mkdir()
    for i, (lat, lon) in enumerate(points):
        path = root / f"scene-{i}.jpg"
        image = Image.new("RGB", (640, 480), ["navy", "darkgreen", "maroon"][i % 3])
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (20 + i * 70, 50, 250 + i * 70, 350),
            fill=["yellow", "cyan", "white"][i % 3],
        )
        draw.text((60, 70), f"Synthetic Geo scene {i}", fill="black")
        image.save(path)
        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                f"-GPSLatitude={lat}",
                "-GPSLatitudeRef=N",
                f"-GPSLongitude={lon}",
                "-GPSLongitudeRef=E",
                "-GPSMapDatum=WGS-84",
                f"-DateTimeOriginal=2026:09:{1 + i * 4:02} 12:00:00",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}


def config(path, proxy_url, ca):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[geo_network]\nproxy_url={json.dumps(proxy_url)}\nca_bundle={json.dumps(str(ca))}\nminimum_interval_seconds=0.01\n"
    )


async def scenario(
    host, root, ca, first_proxy, second_proxy, points, *, recover=False, google=True
):
    root.mkdir()
    source = root / "source"
    before = media(source, points)
    workspace = root / "workspace"
    configuration = root / "config" / "config.toml"
    config(configuration, first_proxy, ca)
    environment = {
        "PATH": os.environ["PATH"],
        "MEDIASENSE_CONFIG_HOME": str(configuration.parent),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "AMAP_API_KEY": "synthetic-key",
        "GOOGLE_MAPS_API_KEY": "synthetic-key" if google else "",
        "HTTP_PROXY": first_proxy,
        "HTTPS_PROXY": first_proxy,
        "NO_PROXY": "",
        "no_proxy": "",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    diagnostics = {}
    for name, args in (
        ("version", ["--version"]),
        ("doctor", ["doctor", "--json"]),
        ("tools", ["tools", "list", "--json"]),
    ):
        output = subprocess.run(
            [str(host), *args],
            env=environment,
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        diagnostics[name] = output.strip() if name == "version" else json.loads(output)
    assert "0.10.0" in diagnostics["version"]
    assert diagnostics["doctor"]["status"] == "ok", diagnostics["doctor"]
    assert len(diagnostics["tools"]["tools"]) == 7
    confirmations = []
    responses = []

    async def approve(_context, params):
        confirmations.append(params.message)
        return types.ElicitResult(action="accept", content={})

    params = StdioServerParameters(
        command=str(host), args=["mcp"], cwd=str(root), env=environment
    )
    async with (
        stdio_client(params) as (incoming, outgoing),
        ClientSession(incoming, outgoing, elicitation_callback=approve) as session,
    ):
        await session.initialize()
        assert len((await session.list_tools()).tools) == 7
        opened = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert not opened.is_error, opened
        dataset = opened.structured_content["dataset_ref"]

        async def call(tool, action, **kwargs):
            response = await session.call_tool(
                "mediasense.precheck." + tool,
                {"action": action, "dataset_ref": dataset, **kwargs},
            )
            assert not response.is_error and response.content == [], response
            value = response.structured_content
            assert "error" not in value, value
            responses.append({"tool": tool, "action": action, "response": value})
            return value

        async def drive(ref):
            with anyio.fail_after(120):
                while True:
                    state = await call("run", "status", run_ref=ref)
                    if state["state"] == "running":
                        await anyio.sleep(0.1)
                        continue
                    if state["state"] == "paused":
                        if (
                            state.get("reason", {}).get("code")
                            == "scope_confirmation_required"
                        ):
                            decision = {
                                "kind": "source_scope",
                                "inventory_fingerprint": state["confirmation"][
                                    "inventory_fingerprint"
                                ],
                                "default_disposition": "include",
                                "exceptions": [],
                            }
                        else:
                            decision = "proceed"
                        await call("run", "resume", run_ref=ref, decision=decision)
                        continue
                    return state

        start = await call("run", "start", request_id="request:installed-geo")
        ref = start["run_ref"]
        state = await drive(ref)
        if recover:
            assert state["state"] == "blocked" and "result" not in state, state
            assert state["reason"]["code"] in {
                "geo_provider_unavailable",
                "geo_effect_indeterminate",
            }
            before_recovery = state
            config(configuration, second_proxy, ca)
            # A blocked Run has no pending confirmation yet. This zero-effect
            # resume prepares it; only the subsequent paused confirmation uses proceed.
            await call("run", "resume", run_ref=ref)
            state = await drive(ref)
            assert state["state"] == "completed", state
            assert any(
                second_proxy in message and "recovery_accounting" in message
                for message in confirmations
            )
            diagnostics["blocked_before_recovery"] = before_recovery
        if google:
            assert state["state"] == "completed", state
            review = await call(
                "read",
                "review",
                result_ref=state["result"]["ref"],
                include=["execution_boundary"],
            )
            assert review["result"]["readiness"] == "plan_ready"
            diagnostics["execution_boundary"] = review["execution_boundary"]
            assert review["execution_boundary"]["current_provider_requests"] == (
                9 if recover else len(points)
            ), review["execution_boundary"]
            assert review["execution_boundary"]["billable_calls"] is None
        else:
            assert state["state"] == "blocked" and "result" not in state, state
        diagnostics["final_state"] = state
        diagnostics["confirmation_count"] = len(confirmations)
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    (root / "responses.json").write_text(
        json.dumps(responses, indent=2, ensure_ascii=False)
    )
    (root / "confirmations.json").write_text(
        json.dumps(confirmations, indent=2, ensure_ascii=False)
    )
    return diagnostics


async def exercise(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    certificate, key = root / "loopback-ca.pem", root / "loopback-key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=MediaSense synthetic loopback",
            "-addext",
            "subjectAltName=DNS:maps.googleapis.com,DNS:places.googleapis.com,DNS:restapi.amap.com",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
    )
    with (
        proxy(certificate, key, fail_lat=35.69) as (bad_url, bad_calls),
        proxy(certificate, key) as (good_url, good_calls),
    ):
        mainland = await scenario(
            args.host.resolve(),
            root / "mainland",
            certificate,
            bad_url,
            good_url,
            [(39.9, 116.4)],
        )
        assert len(bad_calls) == 1 and bad_calls[0]["provider"] == "amap", bad_calls
        overseas = await scenario(
            args.host.resolve(),
            root / "overseas",
            certificate,
            bad_url,
            good_url,
            [(35.68, 139.76), (35.69, 139.77), (35.70, 139.78)],
            recover=True,
        )
        assert len(bad_calls) == 7 and len(good_calls) == 3, (bad_calls, good_calls)
        assert [r["operation"] for r in good_calls] == [
            "nearby_places",
            "reverse_geocode",
            "nearby_places",
        ]
        assert all(r["provider"] == "google_maps" for r in bad_calls[1:] + good_calls)
        missing = await scenario(
            args.host.resolve(),
            root / "missing-provider",
            certificate,
            bad_url,
            good_url,
            [(22.3, 114.17)],
            google=False,
        )
        assert len(bad_calls) == 7 and len(good_calls) == 3
    summary = {
        "mainland": mainland,
        "overseas": overseas,
        "missing_provider": missing,
        "first_proxy_requests": bad_calls,
        "recovery_proxy_requests": good_calls,
        "external_map_requests": 0,
        "source_unchanged": True,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )
    print(
        json.dumps(
            {
                "result": "passed",
                "summary": str(root / "summary.json"),
                "loopback_requests": len(bad_calls) + len(good_calls),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    anyio.run(exercise, parser.parse_args())
