# VLESS Collector

Auto-collected **VLESS** configs, deduplicated, cleaned, and **tested through xray**
so only nodes that actually pass traffic are published. Updates every 6 hours via
GitHub Actions.

> First run pending — `sub.txt` and `vless.txt` appear after the workflow runs.

## Subscription

Import this URL into v2rayNG / v2rayN / nekoray / sing-box (base64 subscription):

```
https://raw.githubusercontent.com/mehrdad-tat/vless-collector/main/sub.txt
```

Or the plain list (one config per line):
`https://raw.githubusercontent.com/mehrdad-tat/vless-collector/main/vless.txt`

## How it works

1. Fetch VLESS configs from the sources in `sources.txt` (latest content each run).
2. Keep only `vless://`, drop duplicates and bad hosts (localhost, 127.0.0.1, private IPs).
3. Start xray per node and request `generate_204` through it — keep only live nodes.
4. Sort by latency (fastest first) and publish `sub.txt` + `vless.txt`.

## Run locally

```bash
# needs xray in PATH (or set XRAY_BIN=/path/to/xray)
python main.py
```

Env knobs: `TEST_CONCURRENCY` (default 40), `TEST_TIMEOUT` seconds (8),
`MAX_TEST` cap (0 = no cap), `XRAY_BIN`.

> Configs are sourced from public repositories. Use at your own risk.
