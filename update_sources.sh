#!/bin/bash

set -u

mkdir -p input/JP input/HK input/SG input/extra

# 下载到临时文件，成功后才替换正式文件；失败时保留旧文件。
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

# 主源：Au1rxx 的国家分片。
# 该项目当前说明：发布前已经进行 TCP/TLS/sing-box/HTTP-over-proxy 两轮实测，
# 并按真实 HTTP 延迟排序；这里保留其发布顺序，不再用静态评分重排。
download \
  "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/JP/clash-0001.yaml" \
  "input/JP/clash-0001.yaml" || FAILED=$((FAILED + 1))

download \
  "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/HK/clash-0001.yaml" \
  "input/HK/clash-0001.yaml" || FAILED=$((FAILED + 1))

download \
  "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/SG/clash-0001.yaml" \
  "input/SG/clash-0001.yaml" || FAILED=$((FAILED + 1))

# 第二来源：wzmwayne AIO。
# AIO 是跨地区合并列表，节点已经通过 mihomo generate_204 实测并按延迟排序。
# 这里只补最多 10 个，避免把大量节点塞进 OpenWrt。
download \
  "https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/aio/clash.yaml" \
  "input/extra/wzmwayne-aio.yaml" || FAILED=$((FAILED + 1))

echo "Sources updated; failed downloads: $FAILED"
# 即使某个来源暂时下载失败也不要让 GitHub Actions 因此直接失败：
# filter_nodes.py 会继续使用上一轮仍存在的 input 文件。
exit 0
