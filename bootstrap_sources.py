#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import requests

DOWNLOADS = [
    # general: multi-source, 100 candidates total
    ("https://raw.githubusercontent.com/jifeng250/free-nodes/main/clash.yaml", "input/general/jifeng250-free-nodes.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml", "input/general/yoyapai.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml", "input/general/freesub.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml", "input/general/ripaojiedian.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml", "input/general/passcro.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml", "input/general/anaer.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml", "input/general/xiaoji235.yaml"),
    # chatgpt: six non-Au1rxx public sources
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml", "input/chatgpt/yoyapai.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml", "input/chatgpt/freesub.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml", "input/chatgpt/ripaojiedian.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml", "input/chatgpt/passcro.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml", "input/chatgpt/anaer.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml", "input/chatgpt/xiaoji235.yaml")

def main() -> int:
    failures = 0
    for url, out_name in DOWNLOADS:
        out = Path(out_name)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(f"{out}.tmp")
        print(f"Downloading: {url}")
        try:
            with requests.get(url, timeout=90, stream=True) as response:
                response.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in response.iter_content(1024 * 256):
                        if chunk:
                            fh.write(chunk)
            if not tmp.exists() or tmp.stat().st_size == 0:
                raise RuntimeError("empty download")
            tmp.replace(out)
            print(f"OK: {out} ({out.stat().st_size} bytes)")
        except Exception as exc:
            failures += 1
            print(f"WARN: {url} -> {exc}")
            tmp.unlink(missing_ok=True)
    print(f"Downloads finished; failures={failures}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
