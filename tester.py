"""Actually test vless nodes by routing a request through xray.

For each node we write a tiny xray config (socks inbound -> vless outbound on a
unique local port), start xray, and curl https://www.gstatic.com/generate_204
through the socks port. A 204 within the timeout means the node really works.
"""
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import vless

XRAY_BIN = os.environ.get("XRAY_BIN", "xray")
TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT = float(os.environ.get("TEST_TIMEOUT", "8"))
CONCURRENCY = int(os.environ.get("TEST_CONCURRENCY", "40"))


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _xray_config(node, http_port):
    # http inbound (not socks): urllib speaks to it natively and tunnels https
    # via CONNECT, so we need no third-party socks dependency.
    return {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "port": http_port,
            "listen": "127.0.0.1",
            "protocol": "http",
        }],
        "outbounds": [vless.outbound(node)],
    }


def _curl_through(http_port):
    """Return latency in ms if the proxy serves generate_204, else None."""
    proxy = f"http://127.0.0.1:{http_port}"
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    opener = urllib.request.build_opener(handler)
    start = time.monotonic()
    try:
        resp = opener.open(TEST_URL, timeout=TIMEOUT)
        if resp.status in (204, 200):
            return int((time.monotonic() - start) * 1000)
    except Exception:
        return None
    return None


def test_one(node):
    """Start xray for one node, test it, tear down. Returns latency ms or None."""
    port = _free_port()
    cfg = _xray_config(node, port)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        cfg_path = f.name
    proc = None
    try:
        proc = subprocess.Popen(
            [XRAY_BIN, "run", "-c", cfg_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)  # let xray bind the inbound
        if proc.poll() is not None:
            return None  # xray failed to start (bad config / unsupported)
        return _curl_through(port)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            os.unlink(cfg_path)
        except OSError:
            pass


def test_all(nodes):
    """Test nodes concurrently. Returns list of (node, latency_ms) for live ones."""
    live = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for node, latency in zip(nodes, pool.map(test_one, nodes)):
            if latency is not None:
                live.append((node, latency))
    live.sort(key=lambda nl: nl[1])  # fastest first
    return live
