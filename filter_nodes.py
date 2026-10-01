import glob
import json
import os
import ipaddress
import re

import yaml


OUTPUT = "output/nikki.yaml"
STATS_OUTPUT = "output/filter_stats.json"

# 路由器最终候选池严格控制在 60 个以内：
# 主源 50 个：先经过 Au1rxx 的源站实测，再在云端做结构质量筛选。
# 第二来源最多补 10 个：保留 wzmwayne AIO 自身的测试排序。
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

BAD_WORDS = re.compile(
    r"(expire|expired|traffic|test|trial|free|过期|剩余|流量|到期|官网|免费)",
    re.I,
)

TYPE_SCORE = {
    "vless": 30,
    "hysteria2": 22,
    "tuic": 20,
    "trojan": 16,
    "vmess": 10,
    "ss": 5,
}


def scalar(value):
    return "" if value is None else str(value)


def node_key(node):
    """按连接参数去重，避免同服务器不同凭据/SNI被误合并。"""
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
    """只做结构/协议清洗，不做网络测速。"""
    if not isinstance(node, dict):
        return False

    server = scalar(node.get("server")).strip()
    ntype = scalar(node.get("type")).lower().strip()

    if not server or ntype not in SUPPORTED_TYPES:
        return False

    if server in {"localhost", "local", "127.0.0.1", "::1"}:
        return False

    try:
        addr = ipaddress.ip_address(server)
    except ValueError:
        return True

    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
    )


def score(node):
    """结构质量分：用于云端从已通过源站实测的节点中挑候选。

    这不是速度分；真正的当前网络表现仍由 OpenWrt 的 url-test 决定。
    """
    s = 50
    ntype = scalar(node.get("type")).lower().strip()
    network = scalar(node.get("network")).lower().strip()
    servername = scalar(node.get("servername")).strip()
    sni = scalar(node.get("sni")).strip()
    reality = node.get("reality-opts") or {}
    flow = scalar(node.get("flow")).lower().strip()

    s += TYPE_SCORE.get(ntype, 0)

    if reality:
        s += 20
    if flow == "xtls-rprx-vision":
        s += 15
    if network == "tcp":
        s += 4
    if node.get("tls"):
        s += 5
    if node.get("udp"):
        s += 2

    # TLS/Reality 节点缺少 SNI/ServerName 时，实际兼容性通常更差。
    if (node.get("tls") or reality) and not (servername or sni):
        s -= 25

    # 非 TLS/Reality 的传统节点，作为备用而不是优先项。
    if ntype in {"vmess", "ss"} and not (node.get("tls") or reality):
        s -= 5

    text = f"{node.get('name', '')} {node.get('server', '')}"
    if BAD_WORDS.search(text):
        s -= 60

    return s


def load_yaml_proxies(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return []
    proxies = data.get("proxies", [])
    return proxies if isinstance(proxies, list) else []


def load_main_region(region, seen):
    """主源：源站已实测，云端再按结构质量评分筛选。"""
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

                item = dict(node)
                item["_region"] = region
                item["_source"] = "Au1rxx"
                item["_score"] = score(item)
                item["_source_order"] = len(result)
                result.append(item)
        except Exception as exc:
            print("skip", file_path, exc)

    # 不再相信 country shard 的文件顺序是“质量排名”；
    # 先做结构质量筛选，再以源文件顺序作为稳定的同分 tie-breaker。
    result.sort(key=lambda x: (-x["_score"], x["_source_order"]))

    selected = []
    local_seen = set()
    for item in result:
        key = node_key(item)
        if key in local_seen:
            continue
        local_seen.add(key)
        seen.add(key)
        selected.append(item)
        if len(selected) >= MAIN_LIMITS[region]:
            break

    print(f"{region} main usable: {len(result)}")
    print(f"{region} main selected: {len(selected)}")
    return selected


def load_extra(seen):
    """AIO：保留 wzmwayne 已测试/排序后的文件顺序，最多补 10 个。"""
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

    selected = []
    seen = set()
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
        node.pop("_score", None)
        node.pop("_source_order", None)
        clean.append(node)
        source_counts[source] = source_counts.get(source, 0) + 1

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
        "selection": "Au1rxx source-verified + structural score; wzmwayne AIO order preserved",
    }

    with open(STATS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("Total output:", len(clean))
    print("Source counts:", source_counts)
    print("Saved:", OUTPUT)
    print("Saved:", STATS_OUTPUT)


if __name__ == "__main__":
    main()
