#!/bin/bash

set -u

mkdir -p input/general input/chatgpt

download() {
    url="$1"
    out="$2"
    tmp="${out}.tmp"

    echo "Downloading: $url"

    if curl -L --fail --retry 3 --retry-all-errors \
        --connect-timeout 15 --max-time 180 \
        "$url" -o "$tmp" && [ -s "$tmp" ]; then
        mv "$tmp" "$out"
        echo "OK: $out"
        return 0
    fi

    rm -f "$tmp"
    echo "WARN: download failed, keeping old file: $out"
    return 1
}

FAILED=0

# 普通池：只使用新的独立聚合源，不再使用 Au1rxx。
download   "https://raw.githubusercontent.com/jifeng250/free-nodes/main/clash.yaml"   "input/general/jifeng250-free-nodes.yaml" || FAILED=$((FAILED + 1))

# GPT 专用池：非 Au1rxx 来源。
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml"   "input/chatgpt/yoyapai.yaml" || FAILED=$((FAILED + 1))
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml"   "input/chatgpt/freesub.yaml" || FAILED=$((FAILED + 1))
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml"   "input/chatgpt/ripaojiedian.yaml" || FAILED=$((FAILED + 1))
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml"   "input/chatgpt/passcro.yaml" || FAILED=$((FAILED + 1))
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml"   "input/chatgpt/anaer.yaml" || FAILED=$((FAILED + 1))
download   "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml"   "input/chatgpt/xiaoji235.yaml" || FAILED=$((FAILED + 1))

echo "Sources updated; failed downloads: $FAILED"
exit 0
