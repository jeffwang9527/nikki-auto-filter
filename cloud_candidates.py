#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from pathlib import Path
from typing import Any

import yaml

SOURCES = Path("sources.yaml")
GENERAL_OUT = Path("output/candidates-general.yaml")
CHATGPT_OUT = Path("output/candidates-chatgpt.yaml")
UNION_OUT = Path("output/candidates.yaml")
STATS = Path("output/cloud_stats.json")

SUPPORTED_TYPES = {
    "vless",
    "vmess",
    "trojan",
    "ss",
    "hysteria2",
    "tuic",
    "anytls",
    "http",
    "socks5",
}

# 这里只做明显坏节点/结构过滤，不做网络测试。
OBVIOUS_BAD = re.compile(
    r"(expired|expire|traffic|trial|test|测试|试用|过期|剩余|流量|到期)",
    re.I,
)


def scalar(value: Any) -> str:
    return "" if value is None else str(value)


def node_key(node: dict[str, Any]) -> str:
    reality = node.get("reality-opts") or {}
    ws = node.get("ws-opts") or {}
    grpc = node.get("grpc-opts") or {}
    payload = {
        "type": scalar(node.get("type")).lower(),
        "server": scalar(node.get("server")).lower(),
        "port": scalar(node.get("port")),
        "uuid": scalar(node.get("uuid")),
        "password": scalar(node.get("password")),
        "username": scalar(node.get("username")),
        "cipher": scalar(node.get("cipher")),
        "servername": scalar(node.get("servername") or node.get("sni")),
        "network": scalar(node.get("network")).lower(),
        "path": scalar(node.get("path") or ws.get("path")),
        "flow": scalar(node.get("flow")),
        "grpc_service_name": scalar(
            node.get("service-name") or grpc.get("grpc-service-name")
        ),
        "reality_public_key": scalar(reality.get("public-key")),
        "reality_short_id": scalar(reality.get("short-id")),
    }
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def valid_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    typ = scalar(node.get("type")).lower().strip()
    server = scalar(node.get("server")).strip()

    try:
        port = int(node.get("port"))
    except (TypeError, ValueError):
        return False

    if typ not in SUPPORTED_TYPES or not server or not 1 <= port <= 65535:
        return False
    if server.lower() in {"localhost", "local", "127.0.0.1", "::1"}:
        return False

    try:
        address = ipaddress.ip_address(server)
    except ValueError:
        address = None

    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        return False

    return not OBVIOUS_BAD.search(f"{scalar(node.get('name'))} {server}")


def extract_proxies(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        proxies = value.get("proxies")
        if isinstance(proxies, list):
            return [item for item in proxies if isinstance(item, dict)]

        output: list[dict[str, Any]] = []
        for child in value.values():
            output.extend(extract_proxies(child))
        return output

    if isinstance(value, list):
        output: list[dict[str, Any]] = []
        for child in value:
            output.extend(extract_proxies(child))
        return output

    return []


def read_nodes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[WARN] cannot parse {path}: {exc}")
        return []

    return extract_proxies(data)


def make_name(
    category: str, source: str, region: str, original: str, serial: int
) -> str:
    clean = re.sub(r"\s+", " ", original).strip()[:100] or f"node-{serial:04d}"
    region_part = f" | {region}" if region else ""
    return f"{category} | {source}{region_part} | {clean}"


def build_group(
    entries: list[dict[str, Any]], category: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[str] = set()
    selected: list[dict[str, Any]] = []
    source_stats: dict[str, Any] = {}

    for entry in entries:
        source_id = scalar(entry.get("id"))
        source = scalar(entry.get("source")) or source_id
        region = scalar(entry.get("region"))
        path = Path(scalar(entry.get("path")))
        limit = int(entry.get("limit", 0) or 0)

        raw_nodes = read_nodes(path)
        accepted = 0
        valid = 0
        duplicate = 0
        obvious_bad = 0

        for index, node in enumerate(raw_nodes, 1):
            if not valid_node(node):
                obvious_bad += 1
                continue

            valid += 1
            key = node_key(node)
            if key in seen:
                duplicate += 1
                continue

            seen.add(key)
            item = dict(node)
            item["name"] = make_name(
                category.upper(), source, region, scalar(node.get("name")), index
            )
            item["_nikki_source"] = source
            item["_nikki_source_id"] = source_id
            item["_nikki_category"] = category
            selected.append(item)
            accepted += 1

            if accepted >= limit:
                break

        source_stats[source_id] = {
            "source": source,
            "region": region or None,
            "input": str(path).replace("\\", "/"),
            "valid_seen": valid,
            "duplicates": duplicate,
            "selected": accepted,
            "limit": limit,
        }

    return selected, source_stats


def write_candidates(path: Path, nodes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "proxies": [
            {key: value for key, value in node.items() if not key.startswith("_nikki_")}
            for node in nodes
        ]
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> None:
    if not SOURCES.exists():
        raise SystemExit(f"source registry not found: {SOURCES}")

    registry = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise SystemExit("invalid source registry")

    general_entries = registry.get("general", [])
    chatgpt_entries = registry.get("chatgpt", [])
    if not isinstance(general_entries, list) or not isinstance(chatgpt_entries, list):
        raise SystemExit("sources.yaml must contain general/chatgpt lists")

    general_nodes, general_stats = build_group(general_entries, "general")
    chatgpt_nodes, chatgpt_stats = build_group(chatgpt_entries, "chatgpt")

    # GPT 专用池明确排除 Au1rxx 中已经出现的相同节点。
    general_keys = {node_key(node) for node in general_nodes}
    before_chatgpt = len(chatgpt_nodes)
    chatgpt_nodes = [
        node for node in chatgpt_nodes if node_key(node) not in general_keys
    ]
    removed_cross_source = before_chatgpt - len(chatgpt_nodes)

    # 兼容旧脚本：candidates.yaml 只是两个候选池的合集，不用于最终路由器。
    union_seen = set()
    union_nodes = []
    for node in general_nodes + chatgpt_nodes:
        key = node_key(node)
        if key not in union_seen:
            union_seen.add(key)
            union_nodes.append(node)

    write_candidates(GENERAL_OUT, general_nodes)
    write_candidates(CHATGPT_OUT, chatgpt_nodes)
    write_candidates(UNION_OUT, union_nodes)

    stats = {
        "method": "source-separated dedupe + structural cleanup + obvious-bad filtering only",
        "local_network_tests": False,
        "general_candidate_count": len(general_nodes),
        "chatgpt_candidate_count": len(chatgpt_nodes),
        "candidate_total": len(union_nodes),
        "chatgpt_cross_excluded_from_general": removed_cross_source,
        "source_groups": {
            "general": general_stats,
            "chatgpt": chatgpt_stats,
        },
    }

    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"general candidate nodes: {len(general_nodes)}")
    print(f"chatgpt candidate nodes: {len(chatgpt_nodes)}")
    print(f"combined candidate nodes: {len(union_nodes)}")


if __name__ == "__main__":
    main()
