#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import median
from typing import Any

import requests
import yaml

GENERAL_TESTS = [
    ("gstatic", "https://www.gstatic.com/generate_204", "204", 6500),
    ("github", "https://github.com/", "200-399", 8500),
    ("cloudflare", "https://www.cloudflare.com/cdn-cgi/trace", "200-299", 6500),
]

OPENAI_TESTS = [
    ("chatgpt_edge", "https://chatgpt.com/robots.txt", "200-499", 8500),
    ("auth_edge", "https://auth.openai.com/", "200-499", 8500),
    ("openai_api", "https://api.openai.com/v1/models", "401", 8500),
]

SUCCESS_TTL = 6 * 3600
FAIL_COOLDOWN = 6 * 3600
FAIL_EJECT_STREAK = 3
MAX_SAME_SERVER = 2


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


def server_key(node: dict[str, Any]) -> str:
    return f"{scalar(node.get('server')).lower()}:{scalar(node.get('port'))}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_nodes(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("proxies"), list):
        raise ValueError(f"Invalid candidate YAML: {path}")
    return [node for node in data["proxies"] if isinstance(node, dict)]


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print("[WARN] cache ignored:", exc)
        return {}


def save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def due(state: dict[str, Any], kind: str, full: bool) -> bool:
    last = int(state.get(f"last_{kind}_test", 0) or 0)
    if full or not last:
        return True

    if state.get(f"{kind}_ok"):
        return time.time() - last >= SUCCESS_TTL
    return time.time() - last >= FAIL_COOLDOWN


class MihomoRunner:
    """一个测试周期只启动一个 mihomo，加载需要测试的全部节点。"""

    def __init__(self, binary: str, nodes: list[dict[str, Any]]):
        self.binary = Path(binary)
        self.nodes = nodes
        self.root = Path(tempfile.mkdtemp(prefix="nikki-local-mihomo-"))
        self.config = self.root / "config.yaml"
        self.log = self.root / "mihomo.log"
        self.port = free_port()
        self.secret = hashlib.sha256(os.urandom(32)).hexdigest()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen[str] | None = None

    def start(self) -> None:
        proxies: list[dict[str, Any]] = []
        names: set[str] = set()

        for index, raw in enumerate(self.nodes):
            node = dict(raw)
            name = scalar(node.get("name")).strip() or f"node-{index:04d}"
            if name in names:
                name = f"{name} [{index}]"
            names.add(name)

            # 仅作用于临时测试实例，避免本机/路由器 IPv6 变化。
            node["name"] = name
            node["ip-version"] = "ipv4"
            proxies.append(node)

        config = {
            "mode": "rule",
            "log-level": "warning",
            "ipv6": False,
            "unified-delay": True,
            "tcp-concurrent": True,
            "allow-lan": False,
            "external-controller": f"127.0.0.1:{self.port}",
            "secret": self.secret,
            "proxies": proxies,
        }

        self.config.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        with self.log.open("w", encoding="utf-8") as handle:
            self.proc = subprocess.Popen(
                [str(self.binary), "-f", str(self.config), "-d", str(self.root)],
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(self.root),
            )

        headers = {"Authorization": f"Bearer {self.secret}"}
        deadline = time.time() + 20
        last_error = ""

        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    self.log.read_text(encoding="utf-8", errors="ignore")[-6000:]
                )

            try:
                response = requests.get(
                    f"{self.base}/version", headers=headers, timeout=1.5
                )
                if response.ok:
                    return
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)

            time.sleep(0.25)

        raise TimeoutError(f"mihomo API not ready: {last_error}")

    def delay(
        self, name: str, url: str, timeout_ms: int, expected: str
    ) -> int | None:
        encoded = urllib.parse.quote(name, safe="")
        headers = {"Authorization": f"Bearer {self.secret}"}

        try:
            response = requests.get(
                f"{self.base}/proxies/{encoded}/delay",
                params={
                    "url": url,
                    "timeout": timeout_ms,
                    "expected": expected,
                },
                headers=headers,
                timeout=(2, timeout_ms / 1000 + 2),
            )
            if response.status_code != 200:
                return None

            delay_ms = response.json().get("delay")
            if isinstance(delay_ms, int) and delay_ms > 0:
                return delay_ms
        except (requests.RequestException, ValueError, TypeError):
            pass

        return None

    def close(self) -> None:
        try:
            if self.proc is not None:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        except Exception:
            try:
                if self.proc is not None:
                    self.proc.kill()
            except Exception:
                pass

        shutil.rmtree(self.root, ignore_errors=True)


def test_kind(
    runner: MihomoRunner,
    node_name: str,
    tests: list[tuple[str, str, str, int]],
) -> tuple[bool, dict[str, int], int]:
    delays: dict[str, int] = {}
    for label, url, expected, timeout in tests:
        delay_ms = runner.delay(node_name, url, timeout, expected)
        if delay_ms is None:
            return False, delays, int(time.time())
        delays[label] = delay_ms
    return True, delays, int(time.time())


def update_kind(
    state: dict[str, Any],
    runner: MihomoRunner,
    kind: str,
    full: bool,
) -> None:
    tests = GENERAL_TESTS if kind == "general" else OPENAI_TESTS
    ok, delays, now = test_kind(runner, state["name"], tests)

    state[f"last_{kind}_test"] = now
    state[f"{kind}_ok"] = ok
    state[f"{kind}_delays"] = delays

    if ok:
        value = int(median(delays.values()))
        state[f"{kind}_median"] = value
        state[f"{kind}_consecutive_success"] = (
            int(state.get(f"{kind}_consecutive_success", 0)) + 1
        )
        state[f"{kind}_consecutive_fail"] = 0
        state[f"{kind}_last_success"] = now
        state[f"{kind}_last_success_median"] = value
    else:
        state[f"{kind}_median"] = None
        state[f"{kind}_consecutive_fail"] = (
            int(state.get(f"{kind}_consecutive_fail", 0)) + 1
        )
        state[f"{kind}_consecutive_success"] = 0


def run_probe(
    runner: MihomoRunner,
    node: dict[str, Any],
    previous: dict[str, Any],
    kinds: set[str],
    full: bool,
) -> dict[str, Any]:
    state = dict(previous)
    state["name"] = scalar(node.get("name"))

    for kind in sorted(kinds):
        if due(state, kind, full):
            update_kind(state, runner, kind, full)

    state["last_run"] = int(time.time())
    return state


def eligible(state: dict[str, Any], kind: str) -> tuple[bool, bool]:
    if state.get(f"{kind}_ok"):
        return True, False

    grace = (
        int(state.get(f"{kind}_consecutive_fail", 0)) < FAIL_EJECT_STREAK
        and int(state.get(f"{kind}_last_success", 0)) > 0
    )
    return grace, grace


def pick(
    items: list[tuple[dict[str, Any], dict[str, Any], bool]],
    limit: int,
    metric: str,
) -> list[tuple[dict[str, Any], dict[str, Any], bool]]:
    def rank(item):
        node, state, grace = item
        delay_ms = state.get(metric)
        if delay_ms is None:
            fallback = (
                "general_last_success_median"
                if metric == "general_median"
                else "openai_last_success_median"
            )
            delay_ms = state.get(fallback, 999999)
        return (1 if grace else 0, float(delay_ms or 999999), scalar(node.get("name")))

    chosen: list[tuple[dict[str, Any], dict[str, Any], bool]] = []
    servers: dict[str, int] = {}

    for node, state, grace in sorted(items, key=rank):
        server = server_key(node)
        if servers.get(server, 0) >= MAX_SAME_SERVER:
            continue

        chosen.append((node, state, grace))
        servers[server] = servers.get(server, 0) + 1
        if len(chosen) >= limit:
            break

    return chosen


def write_yaml(path: Path, nodes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        yaml.safe_dump({"proxies": nodes}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for node in nodes:
        key = node_key(node)
        if key not in seen:
            seen.add(key)
            output.append(node)
    return output


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mihomo", required=True)
    ap.add_argument(
        "--general-candidate", default="output/candidates-general.yaml"
    )
    ap.add_argument(
        "--chatgpt-candidate", default="output/candidates-chatgpt.yaml"
    )
    ap.add_argument("--cache", default="cache/node-cache.json")
    ap.add_argument("--report", default="output/local-test-report.json")
    ap.add_argument("--general-out", default="output/nikki-general.yaml")
    ap.add_argument("--chatgpt-out", default="output/nikki-chatgpt.yaml")
    ap.add_argument("--union-out", default="output/nikki.yaml")
    ap.add_argument("--general-limit", type=int, default=12)
    ap.add_argument("--chatgpt-limit", type=int, default=8)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    general_candidates = dedupe_nodes(load_nodes(Path(args.general_candidate)))
    chatgpt_candidates = dedupe_nodes(load_nodes(Path(args.chatgpt_candidate)))

    # 建立“节点 -> 需要测试的用途集合”。
    # 普通节点只测普通目标，GPT 专用节点只测 OpenAI/ChatGPT 目标；
    # 若将来两个来源集合发生重叠，则同一个 mihomo 实例里分别测两套目标。
    tasks: dict[str, tuple[dict[str, Any], set[str]]] = {}

    for node in general_candidates:
        key = node_key(node)
        if key not in tasks:
            tasks[key] = (node, set())
        tasks[key][1].add("general")

    for node in chatgpt_candidates:
        key = node_key(node)
        if key not in tasks:
            tasks[key] = (node, set())
        tasks[key][1].add("openai")

    cache = load_cache(Path(args.cache))
    results = dict(cache)

    to_test: list[tuple[dict[str, Any], set[str]]] = []
    for key, (node, kinds) in tasks.items():
        state = cache.get(key, {})
        due_kinds = {kind for kind in kinds if due(state, kind, args.full)}
        if due_kinds:
            to_test.append((node, due_kinds))

    print(
        f"[local] general_candidates={len(general_candidates)} "
        f"chatgpt_candidates={len(chatgpt_candidates)} "
        f"to_test={len(to_test)} cache_entries={len(cache)} "
        f"concurrency={args.concurrency}"
    )

    if to_test:
        runner = MihomoRunner(
            args.mihomo, [node for node, _ in to_test]
        )
        runner.start()
        try:
            with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
                futures = {
                    pool.submit(
                        run_probe,
                        runner,
                        node,
                        cache.get(node_key(node), {}),
                        kinds,
                        args.full,
                    ): (node, kinds)
                    for node, kinds in to_test
                }

                for index, future in enumerate(as_completed(futures), 1):
                    node, kinds = futures[future]
                    key = node_key(node)
                    try:
                        results[key] = future.result()
                    except Exception as exc:
                        fallback = dict(cache.get(key, {}))
                        fallback["name"] = scalar(node.get("name"))
                        fallback["error"] = str(exc)
                        fallback["last_run"] = int(time.time())
                        results[key] = fallback

                    print(
                        f"[local] {index}/{len(to_test)} "
                        f"{scalar(node.get('name'))}"
                    )
        finally:
            runner.close()

    save_cache(Path(args.cache), results)

    general_eligible: list[tuple[dict[str, Any], dict[str, Any], bool]] = []
    chatgpt_eligible: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    for node in general_candidates:
        state = results.get(node_key(node), {})
        ok, grace = eligible(state, "general")
        if ok:
            general_eligible.append((node, state, grace))

    for node in chatgpt_candidates:
        state = results.get(node_key(node), {})
        ok, grace = eligible(state, "openai")
        if ok:
            chatgpt_eligible.append((node, state, grace))

    # 两个池独立选择，不再互相排斥。
    general_pick = pick(general_eligible, args.general_limit, "general_median")
    chatgpt_pick = pick(chatgpt_eligible, args.chatgpt_limit, "openai_median")

    general_out = [
        {**node, "name": f"GEN | {scalar(node.get('name'))}"}
        for node, _, _ in general_pick
    ]
    chatgpt_out = [
        {**node, "name": f"GPT | {scalar(node.get('name'))}"}
        for node, _, _ in chatgpt_pick
    ]

    # 路由器只消费这三个小文件；candidates-* 仍然只是本地测速前的候选池。
    write_yaml(Path(args.general_out), general_out)
    write_yaml(Path(args.chatgpt_out), chatgpt_out)
    write_yaml(Path(args.union_out), general_out + chatgpt_out)

    general_tested_now = sum(
        1 for _, kinds in to_test if "general" in kinds
    )
    chatgpt_tested_now = sum(
        1 for _, kinds in to_test if "openai" in kinds
    )

    report = {
        "timestamp": int(time.time()),
        "general_candidate_count": len(general_candidates),
        "chatgpt_candidate_count": len(chatgpt_candidates),
        "candidate_count": len(tasks),
        "tested_now": len(to_test),
        "general_tested_now": general_tested_now,
        "chatgpt_tested_now": chatgpt_tested_now,
        "cache_reused": max(0, len(tasks) - len(to_test)),
        "general_eligible": len(general_eligible),
        "openai_edge_eligible": len(chatgpt_eligible),
        "selected_general": len(general_out),
        "selected_chatgpt": len(chatgpt_out),
        "selected_total": len(general_out) + len(chatgpt_out),
        "policy": {
            "general_limit": args.general_limit,
            "chatgpt_limit": args.chatgpt_limit,
            "concurrency": args.concurrency,
            "success_retest_hours": SUCCESS_TTL / 3600,
            "failure_cooldown_hours": FAIL_COOLDOWN / 3600,
            "failure_eject_streak": FAIL_EJECT_STREAK,
            "max_same_server": MAX_SAME_SERVER,
            "pool_selection_independent": True,
        },
        "selection_sources": {
            "general": "output/candidates-general.yaml (Au1rxx only)",
            "chatgpt": "output/candidates-chatgpt.yaml (non-Au1rxx sources only)",
        },
        "selected": {
            "general": [
                {
                    "name": scalar(node.get("name")),
                    "delay_ms": state.get("general_median")
                    or state.get("general_last_success_median"),
                    "grace": grace,
                }
                for node, state, grace in general_pick
            ],
            "chatgpt": [
                {
                    "name": scalar(node.get("name")),
                    "delay_ms": state.get("openai_median")
                    or state.get("openai_last_success_median"),
                    "grace": grace,
                }
                for node, state, grace in chatgpt_pick
            ],
        },
        "note": (
            "OpenAI/ChatGPT result is transport/edge reachability from this "
            "Windows network; it does not guarantee login, websocket, "
            "streaming, or long-term stability."
        ),
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "general_candidate_count",
                    "chatgpt_candidate_count",
                    "candidate_count",
                    "tested_now",
                    "cache_reused",
                    "general_eligible",
                    "openai_edge_eligible",
                    "selected_general",
                    "selected_chatgpt",
                    "selected_total",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
