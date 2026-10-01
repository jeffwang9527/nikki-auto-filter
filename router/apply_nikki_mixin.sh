#!/bin/sh
set -eu

MIXIN_URL="https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/router/nikki-mixin.yaml"
MIXIN_FILE="/etc/nikki/mixin.yaml"

echo "[1/4] Download Nikki pool mixin"
tmp="${MIXIN_FILE}.tmp"
wget -q -O "$tmp" "$MIXIN_URL"
test -s "$tmp"
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
echo "General provider: https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/output/nikki-general.yaml"
echo "GPT provider:     https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/output/nikki-chatgpt.yaml"
echo "Provider refresh: 14400s (4h)"
echo "Health check:     300s (5m)"
echo
echo "Verify with: uci show nikki.mixin; logread -e nikki | tail -n 80"
