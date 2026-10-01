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

# 普通池：free18 + Barabama + Ruk1ng + ripaojiedian + anaer + yoyapai。
download "https://raw.githubusercontent.com/free18/v2ray/main/c.yaml" "input/general/free18.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/Barabama/FreeNodes/main/nodes/clashmeta.yaml" "input/general/barabama-clashmeta.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml" "input/general/freesub.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash" "input/general/ripaojiedian.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml" "input/general/anaer.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml" "input/general/yoyapai.yaml" || FAILED=$((FAILED + 1))

# GPT 专用池：与普通池允许重叠。
download "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml" "input/chatgpt/yoyapai.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml" "input/chatgpt/freesub.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash" "input/chatgpt/ripaojiedian.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml" "input/chatgpt/anaer.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/free18/v2ray/main/c.yaml" "input/chatgpt/free18.yaml" || FAILED=$((FAILED + 1))
download "https://raw.githubusercontent.com/Barabama/FreeNodes/main/nodes/clashmeta.yaml" "input/chatgpt/barabama-clashmeta.yaml" || FAILED=$((FAILED + 1))

echo "Sources updated; failed downloads: $FAILED"
exit 0
