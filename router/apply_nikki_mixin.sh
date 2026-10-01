#!/bin/sh
set -eu

MIXIN_URL="https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/router/nikki-mixin.yaml"
MIXIN_FILE="/etc/nikki/mixin.yaml"

echo "[1/4] Download Nikki pool mixin"
tmp="${MIXIN_FILE}.tmp"
wget -q -O "$tmp" "$MIXIN_URL"
test -s "$tmp"
mv "$tmp" "$MIXIN_FILE"

echo "[2/4] Enable Nikki mixin file"
uci set nikki.mixin.mixin_file_content='1'

echo "[3/4] Keep router-facing profile remote, but let proxy-providers fetch the two small pools"
# Do not replace the user's existing profile/routing rules here.
# The mixin adds two remote proxy-providers and OpenAI/ChatGPT rules.
uci commit nikki

echo "[4/4] Validate and reload Nikki"
/etc/init.d/nikki reload

echo
echo "Nikki pool mixin installed."
echo "General pool: https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/output/nikki-general.yaml"
echo "GPT pool:     https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main/output/nikki-chatgpt.yaml"
echo "Provider refresh interval: 14400s (4h)"
echo "Provider health-check interval: 300s (5m)"
