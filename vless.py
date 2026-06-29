"""Parse vless:// URIs and build xray outbound JSON for testing.

A vless URI looks like:
    vless://<uuid>@<host>:<port>?type=ws&security=tls&sni=a.com&path=/x#name
We parse it into a dict and can render a minimal xray outbound that, paired with
a local socks inbound, lets us actually route traffic through the node.
"""
from urllib.parse import urlsplit, parse_qs, unquote
import ipaddress

# Hosts that are never real reachable proxies.
_BAD_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::", ""}


def parse(uri):
    """Return a dict describing the vless node, or None if it is malformed."""
    if not uri.startswith("vless://"):
        return None
    try:
        parts = urlsplit(uri)
    except ValueError:
        return None
    uuid = unquote(parts.username or "")
    host = parts.hostname or ""
    port = parts.port
    if not uuid or not host or not port:
        return None
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    return {
        "uri": uri.split("#")[0].strip(),  # canonical form without remark
        "uuid": uuid,
        "host": host,
        "port": int(port),
        "params": q,
    }


def is_clean(node):
    """False for localhost, private, or otherwise unusable addresses."""
    host = node["host"].lower()
    if host in _BAD_HOSTS:
        return False
    if not (0 < node["port"] < 65536):
        return False
    # Drop private / loopback / reserved IPs. Domain names pass through.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_unspecified:
            return False
    except ValueError:
        pass  # not an IP literal -> a hostname, keep it
    return True


def dedupe_key(node):
    """Two configs pointing at the same endpoint+uuid are the same node."""
    return (node["uuid"], node["host"], node["port"])


def outbound(node):
    """Build an xray outbound object that connects through this node."""
    p = node["params"]
    network = p.get("type", "tcp")
    security = p.get("security", "none")

    stream = {"network": network, "security": security}

    if security == "tls":
        stream["tlsSettings"] = {
            "serverName": p.get("sni", p.get("host", node["host"])),
            "fingerprint": p.get("fp", "chrome"),
            "allowInsecure": False,
        }
        if p.get("alpn"):
            stream["tlsSettings"]["alpn"] = p["alpn"].split(",")
    elif security == "reality":
        stream["realitySettings"] = {
            "serverName": p.get("sni", ""),
            "fingerprint": p.get("fp", "chrome"),
            "publicKey": p.get("pbk", ""),
            "shortId": p.get("sid", ""),
            "spiderX": p.get("spx", ""),
        }

    if network == "ws":
        stream["wsSettings"] = {
            "path": p.get("path", "/"),
            "headers": {"Host": p.get("host", "")} if p.get("host") else {},
        }
    elif network == "grpc":
        stream["grpcSettings"] = {"serviceName": p.get("serviceName", "")}
    elif network in ("http", "h2"):
        stream["network"] = "http"
        stream["httpSettings"] = {
            "path": p.get("path", "/"),
            "host": [p["host"]] if p.get("host") else [],
        }
    elif network == "tcp" and p.get("headerType") == "http":
        stream["tcpSettings"] = {"header": {"type": "http"}}

    user = {"id": node["uuid"], "encryption": p.get("encryption", "none")}
    if p.get("flow"):
        user["flow"] = p["flow"]

    return {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": node["host"],
                "port": node["port"],
                "users": [user],
            }]
        },
        "streamSettings": stream,
    }
