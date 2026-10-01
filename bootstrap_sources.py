#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import requests

DOWNLOADS = [
    # general: Au1rxx only
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-JP.yaml", "input/general/au1rxx-jp.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-HK.yaml", "input/general/au1rxx-hk.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-SG.yaml", "input/general/au1rxx-sg.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-US.yaml", "input/general/au1rxx-us.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-DE.yaml", "input/general/au1rxx-de.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-KR.yaml", "input/general/au1rxx-kr.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-TW.yaml", "input/general/au1rxx-tw.yaml"),
    ("https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/by-country/clash-CA.yaml", "input/general/au1rxx-ca.yaml"),
    # chatgpt: non-Au1rxx sources only
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml", "input/chatgpt/yoyapai.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml", "input/chatgpt/freesub.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml", "input/chatgpt/ripaojiedian.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml", "input/chatgpt/passcro.yaml"),
    ("https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml", "input/chatgpt/anaer.yaml"),
    ("https://raw.githubusercontent.com/xiaoji235/airport-free/main/clash/clashnodecc.txt", "input/chatgpt/xiaoji235.yaml"),
]

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
