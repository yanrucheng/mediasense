"""Real loopback HTTP verifies effective Geo proxy configuration without map access."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from mediasense.geo import UrllibJsonTransport, GeoTransientError


@contextmanager
def server(*, delay=0, status=200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 429:
                self.send_header("Retry-After", "2")
            self.end_headers()
            try:
                self.wfile.write(json.dumps({"loopback": True}).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    worker.start()
    try:
        yield httpd.server_address[1], requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=1)


def test_explicit_proxy_reaches_loopback_and_disclosure_redacts_password(monkeypatch):
    monkeypatch.setattr("mediasense.geo.getproxies", lambda: {})
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    with server() as (port, requests):
        transport = UrllibJsonTransport(
            proxy_url=f"http://user:private-password@127.0.0.1:{port}", configured=True
        )
        response = transport.get_json(
            "http://synthetic.invalid/geo",
            params={"latitude": "35", "key": "synthetic"},
            timeout=1,
        )
        assert response == {"loopback": True}
        assert requests[0].startswith("http://synthetic.invalid/geo?")
        assert "private-password" not in repr(transport.network_profile)
        assert transport.network_profile["proxy_receivers"] == [
            f"http://127.0.0.1:{port}"
        ]
        assert transport.network_profile["reachability"] == "not_checked"


def test_no_proxy_bypasses_configured_proxy(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with server() as (port, requests):
        transport = UrllibJsonTransport(proxy_url="http://127.0.0.1:1", configured=True)
        assert transport.get_json(f"http://127.0.0.1:{port}/geo", params={}, timeout=1)[
            "loopback"
        ]
        assert requests == ["/geo?"]


@pytest.mark.parametrize(
    "status,delay,code", [(429, 0, "rate_limited"), (200, 0.1, "transport_timeout")]
)
def test_actual_http_failure_retains_sent_effect_and_classification(
    monkeypatch, status, delay, code
):
    monkeypatch.setattr("mediasense.geo.getproxies", lambda: {})
    with server(status=status, delay=delay) as (port, requests):
        transport = UrllibJsonTransport(configured=True)
        with pytest.raises(GeoTransientError) as failed:
            transport.get_json(f"http://127.0.0.1:{port}/geo", params={}, timeout=0.03)
        assert requests == ["/geo?"]
        assert failed.value.failure_code == code
        assert failed.value.request_count == 1
        assert failed.value.safe_to_retry is (status == 429)
        if status == 429:
            assert failed.value.retry_after == 2
