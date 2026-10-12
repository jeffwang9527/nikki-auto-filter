#!/bin/sh
set -eu

# Pin exact commit f137593 so the router always pulls the same verified mixin version.
# Update this hash whenever the mixin/provider URLs change upstream.
MIXIN_URL="https://fastly.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@f137593/router/nikki-mixin.yaml"
MIXIN_FILE="/etc/nikki/mixin.yaml"

echo "[1/4] Download Nikki pool mixin"
tmp="${MIXIN_FILE}.tmp"
curl -4 -fsSL --connect-timeout 10 --max-time 30 "$MIXIN_URL" -o "$tmp"
test -s "$tmp"

if cmp -s "$tmp" "$MIXIN_FILE"; then
    rm -f "$tmp"
    echo "mixin unchanged, skip reload"
    exit 0
fi
mv "$tmp" "$MIXIN_FILE"

echo "[2/4] Enable Nikki mixin processing"
if ! uci get nikki.mixin.mixin_file_content >/dev/null 2>&1; then
    uci set nikki.mixin=mixin
fi
uci set nikki.mixin.mixin_file_content="1"

echo "[3/4] Ensure Nikki is not in core-only mode"
uci set nikki.config.core_only="0"
uci set nikki.config.test_profile="1"
uci commit nikki

echo "[4/4] Reload Nikki"
/etc/init.d/nikki reload

echo
echo "Nikki pool mixin installed."
echo "Mixin source:     fastly.jsdelivr.net @c8fceab (contains @f137593 providers)"
echo "General provider: https://fastly.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@f137593/output/nikki-general.yaml"
echo "GPT provider:     https://fastly.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@f137593/output/nikki-chatgpt.yaml"
echo "Provider refresh: 14400s (4h)"
echo "Health check:     300s (5m)"
echo
echo "Verify with: uci show nikki.mixin; logread -e nikki | tail -n 80"
