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

# 普通池：多源候选，共计最多 100 个。
download "https://raw.githubusercontent.com/jifeng250/free-nodes/main/clash.yaml" "input/general/jifeng250-free-nodes.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml" "input/general/yoyapai.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml" "input/general/freesub.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml" "input/general/ripaojiedian.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml" "input/general/passcro.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml" "input/general/anaer.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml" "input/general/xiaoji235.yaml" || FAILED=$((FAILED + 1))

# GPT 专用池：6 个非 Au1rxx 来源，共计最多 72 个。
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml" "input/chatgpt/yoyapai.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml" "input/chatgpt/freesub.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml" "input/chatgpt/ripaojiedian.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml" "input/chatgpt/passcro.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml" "input/chatgpt/anaer.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml" "input/chatgpt/xiaoji235.yaml" || FAILED=$((FAILED + 1))

echo "Sources updated; failed downloads: $FAILED"
exit 0
