import glob
import json
import os
import ipaddress

import yaml


OUTPUT = "output/nikki.yaml"
STATS_OUTPUT = "output/filter_stats.json"

# 路由器最终候选池严格控制在 60 个以内：
# 主源保留 50 个（Au1rxx 已经按实际 HTTP/HTTPS 测试结果排序），
# 第二来源最多补 10 个，提供来源多样性和备用节点。
MAIN_LIMITS = {
    "JP": 20,
    "HK": 20,
    "SG": 10,
}
EXTRA_LIMIT = 10
EXTRA_SOURCE = "input/extra/wzmwayne-aio.yaml"

SUPPORTED_TYPES = {
    "vless",
    "vmess",
    "trojan",
    "ss",
    "hysteria2",
    "tuic",
}


def scalar(value):
    return "" if value is None else str(value)


def node_key(node):
    """按真实连接参数去重，避免误删同服务器不同凭据/SNI 的节点。"""
    reality = node.get("reality-opts") or {}
    return (
        scalar(node.get("server")),
        scalar(node.get("port")),
        scalar(node.get("type")).lower(),
        scalar(node.get("uuid")),
        scalar(node.get("password")),
        scalar(node.get("username")),
        scalar(node.get("servername")),
        scalar(node.get("sni")),
        scalar(node.get("network")),
        scalar(node.get("path")),
        scalar(reality.get("public-key")),
        scalar(reality.get("short-id")),
    )


def valid_node(node):
    """只做结构/协议清洗；不再用静态分数打乱源站已经测试好的排序。"""
    if not isinstance(node, dict):
        return False

    server = scalar(node.get("server")).strip()
    ntype = scalar(node.get("type")).lower().strip()

    if not server or ntype not in SUPPORTED_TYPES:
        return False

    # AIO 文件前面有若干说明用 dummy 节点。
    if server in {"localhost", "local", "127.0.0.1", "::1"}:
        return False

    try:
        addr = ipaddress.ip_address(server)
    except ValueError:
        # 域名，保留。
        return True

    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    )


def load_yaml_proxies(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return []

    proxies = data.get("proxies", [])
    return proxies if isinstance(proxies, list) else []


def load_main_region(region, seen):
    """
    Au1rxx 的 country/clash 文件已经经过其自身的 TCP/TLS/sing-box/
    HTTP-over-proxy 实测，并按真实 HTTP 延迟排序。
    因此这里直接保留文件顺序，只做去重和基础结构清洗。
    """
    result = []
    files = sorted(glob.glob(f"input/{region}/*.yaml"))

    print(f"{region} main source files: {len(files)}")

    for file_path in files:
        try:
            for node in load_yaml_proxies(file_path):
                if not valid_node(node):
                    continue

                key = node_key(node)
                if key in seen:
                    continue

                seen.add(key)
                item = dict(node)
                item["_region"] = region
                item["_source"] = "Au1rxx"
                result.append(item)

                if len(result) >= MAIN_LIMITS[region]:
                    break

        except Exception as exc:
            print("skip", file_path, exc)

        if len(result) >= MAIN_LIMITS[region]:
            break

    print(f"{region} main selected: {len(result)}")
    return result


def load_extra(seen):
    """
    wzmwayne AIO 已按 mihomo generate_204 实测并按延迟排序。
    AIO 是跨地区列表，所以不强行猜测 JP/HK/SG；这些节点统一标记 EXTRA，
    只进入总 AUTO 候选池。这样不会因为错误的地区识别把好节点丢掉。
    """
    result = []

    if not os.path.exists(EXTRA_SOURCE):
        print(f"extra source missing: {EXTRA_SOURCE}")
        return result

    try:
        proxies = load_yaml_proxies(EXTRA_SOURCE)
    except Exception as exc:
        print("skip extra source", EXTRA_SOURCE, exc)
        return result

    for node in proxies:
        if not valid_node(node):
            continue

        key = node_key(node)
        if key in seen:
            continue

        seen.add(key)
        item = dict(node)
        item["_region"] = "EXTRA"
        item["_source"] = "wzmwayne-AIO"
        result.append(item)

        if len(result) >= EXTRA_LIMIT:
            break

    print(f"extra selected: {len(result)}")
    return result


def public_node_name(node, prefix):
    original = scalar(node.get("name")).strip() or "unknown"
    return f"{prefix} | {original}"


def main():
    os.makedirs("output", exist_ok=True)

    seen = set()
    selected = []
    region_counts = {region: 0 for region in MAIN_LIMITS}

    for region in ("JP", "HK", "SG"):
        nodes = load_main_region(region, seen)
        for node in nodes:
            node["name"] = public_node_name(node, region)
            selected.append(node)
            region_counts[region] += 1

    extra_nodes = load_extra(seen)
    for node in extra_nodes:
        node["name"] = public_node_name(node, "EXTRA")
        selected.append(node)

    clean = []
    source_counts = {
        "Au1rxx": 0,
        "wzmwayne-AIO": 0,
    }

    for node in selected:
        source = node.pop("_source", "unknown")
        node.pop("_region", None)
        clean.append(node)
        source_counts[source] = source_counts.get(source, 0) + 1

    # Provider 中只需要 proxies；路由器自己的 subscription.yaml 负责 AUTO。
    with open(OUTPUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"proxies": clean},
            f,
            allow_unicode=True,
            sort_keys=False,
        )

    stats = {
        "total": len(clean),
        "max_total": sum(MAIN_LIMITS.values()) + EXTRA_LIMIT,
        "main_limits": MAIN_LIMITS,
        "region_counts": region_counts,
        "source_counts": source_counts,
        "extra_limit": EXTRA_LIMIT,
        "extra_source": EXTRA_SOURCE,
    }

    with open(STATS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("Total output:", len(clean))
    print("Source counts:", source_counts)
    print("Saved:", OUTPUT)
    print("Saved:", STATS_OUTPUT)


if __name__ == "__main__":
    main()
