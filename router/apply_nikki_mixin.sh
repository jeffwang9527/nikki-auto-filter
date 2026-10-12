#!/bin/sh
set -eu

# Pull mixin + node pools from raw.githubusercontent.com @main: no CDN cache
# delay, so every publish push takes effect on the next apply run.
# Providers are file-type loaded from /etc/nikki/run/ (mihomo never downloads
# them itself) -> avoids jsDelivr @main stale cache, raw EOF resets, and the
# manual commit-hash maintenance of the old pinned-CD approach.

RAW_BASE="https://raw.githubusercontent.com/jeffwang9527/nikki-auto-filter/main"
MIXIN_URL="$RAW_BASE/router/nikki-mixin.yaml"
GENERAL_URL="$RAW_BASE/output/nikki-general.yaml"
GPT_URL="$RAW_BASE/output/nikki-chatgpt.yaml"
MIXIN_FILE="/etc/nikki/mixin.yaml"
RUN_DIR="/etc/nikki/run"
CHANGED=0

fetch() {
    url="$1"
    dst="$2"
    tmp="${dst}.tmp"
    curl -4 -fsSL --connect-timeout 10 --max-time 30 "$url" -o "$tmp"
    if [ -f "$dst" ] && cmp -s "$tmp" "$dst"; then
        rm -f "$tmp"
    else
        mv -f "$tmp" "$dst"
        CHANGED=1
    fi
}

echo "[1/4] Download Nikki pool mixin"
fetch "$MIXIN_URL" "$MIXIN_FILE"

echo "[2/4] Download node pools (raw, no CDN cache)"
mkdir -p "$RUN_DIR"
fetch "$GENERAL_URL" "$RUN_DIR/nikki-general.yaml"
fetch "$GPT_URL" "$RUN_DIR/nikki-chatgpt.yaml"

if [ "$CHANGED" -eq 0 ]; then
    echo "mixin and pools unchanged, skip reload"
    exit 0
fi

echo "[3/4] Enable Nikki mixin processing"
if ! uci get nikki.mixin.mixin_file_content >/dev/null 2>&1; then
    uci set nikki.mixin=mixin
fi
uci set nikki.mixin.mixin_file_content="1"
uci set nikki.config.core_only="0"
uci set nikki.config.test_profile="1"
uci commit nikki

echo "[4/4] Reload Nikki"
/etc/init.d/nikki reload

echo
echo "Nikki pool mixin installed."
echo "Mixin source: raw.githubusercontent.com @main (no CDN cache)"
echo "General pool: $RUN_DIR/nikki-general.yaml (file provider)"
echo "GPT pool:     $RUN_DIR/nikki-chatgpt.yaml (file provider)"
echo "Health check: 300s (5m)"
echo
echo "Verify with: uci show nikki.mixin; logread -e nikki | tail -n 80"
