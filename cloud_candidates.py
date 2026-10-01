#!/usr/bin/env python3
from __future__ import annotations
import hashlib, ipaddress, json, re
from pathlib import Path
from typing import Any
import yaml

OUTPUT=Path("output/candidates.yaml")
STATS=Path("output/cloud_stats.json")
SUPPORTED_TYPES={"vless","vmess","trojan","ss","hysteria2","tuic","anytls","http","socks5"}
AU1RXX_LIMITS={"JP":20,"HK":20,"SG":20}
EXTRA_LIMITS={"wzmwayne":8,"freesubscheck":4,"passcro":4,"nomorewalls":4}
OBVIOUS_BAD=re.compile(r"(expired|expire|traffic|trial|test|测试|试用|过期|剩余|流量|到期|官网|免费)",re.I)

def scalar(v:Any)->str:
    return "" if v is None else str(v)

def node_key(n:dict[str,Any])->str:
    r=n.get("reality-opts") or {}; w=n.get("ws-opts") or {}; g=n.get("grpc-opts") or {}
    payload={"type":scalar(n.get("type")).lower(),"server":scalar(n.get("server")).lower(),"port":scalar(n.get("port")),
             "uuid":scalar(n.get("uuid")),"password":scalar(n.get("password")),"username":scalar(n.get("username")),
             "cipher":scalar(n.get("cipher")),"servername":scalar(n.get("servername") or n.get("sni")),
             "network":scalar(n.get("network")).lower(),"path":scalar(n.get("path") or w.get("path")),"flow":scalar(n.get("flow")),
             "grpc_service_name":scalar(n.get("service-name") or g.get("grpc-service-name")),
             "reality_public_key":scalar(r.get("public-key")),"reality_short_id":scalar(r.get("short-id"))}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def valid_node(n:Any)->bool:
    if not isinstance(n,dict): return False
    typ=scalar(n.get("type")).lower().strip(); server=scalar(n.get("server")).strip()
    try: port=int(n.get("port"))
    except(TypeError,ValueError): return False
    if typ not in SUPPORTED_TYPES or not server or not 1<=port<=65535: return False
    if server.lower() in {"localhost","local","127.0.0.1","::1"}: return False
    try: a=ipaddress.ip_address(server)
    except ValueError: a=None
    if a and (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_unspecified): return False
    return not OBVIOUS_BAD.search(f"{scalar(n.get('name'))} {server}")

def extract(x:Any)->list[dict[str,Any]]:
    if isinstance(x,dict):
        if isinstance(x.get("proxies"),list): return [i for i in x["proxies"] if isinstance(i,dict)]
        out=[]
        for v in x.values(): out+=extract(v)
        return out
    if isinstance(x,list):
        out=[]
        for v in x: out+=extract(v)
        return out
    return []

def name_for(source:str,region:str,original:str,serial:int)->str:
    clean=re.sub(r"\s+"," ",original).strip()[:100] or f"node-{serial:04d}"
    return f"{region or source.upper()} | {source} | {clean}"

def main():
    seen=set();selected=[];stats={}
    for region,limit in AU1RXX_LIMITS.items():
        count=0
        for p in sorted(Path(f"input/{region}").glob("*.yaml")):
            try: nodes=extract(yaml.safe_load(p.read_text(encoding="utf-8-sig")))
            except Exception as e: print("[WARN]",p,e); continue
            for i,n in enumerate(nodes,1):
                if not valid_node(n): continue
                k=node_key(n)
                if k in seen: continue
                seen.add(k); item=dict(n); item["name"]=name_for("Au1rxx",region,scalar(n.get("name")),i)
                selected.append(item); count+=1
                if count>=limit: break
            if count>=limit: break
        stats[f"Au1rxx:{region}"]={"selected":count,"limit":limit}
    extra_paths={"wzmwayne":Path("input/extra/wzmwayne-aio.yaml"),
                 "freesubscheck":Path("input/extra/freesubscheck.yaml"),
                 "passcro":Path("input/extra/passcro.yaml"),
                 "nomorewalls":Path("input/extra/nomorewalls.yaml")}
    for source,limit in EXTRA_LIMITS.items():
        count=0; p=extra_paths[source]
        try: nodes=extract(yaml.safe_load(p.read_text(encoding="utf-8-sig"))) if p.exists() else []
        except Exception as e: print("[WARN]",p,e); nodes=[]
        for i,n in enumerate(nodes,1):
            if not valid_node(n): continue
            k=node_key(n)
            if k in seen: continue
            seen.add(k); item=dict(n); item["name"]=name_for(source,"",scalar(n.get("name")),i)
            selected.append(item); count+=1
            if count>=limit: break
        stats[source]={"selected":count,"limit":limit}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(yaml.safe_dump({"proxies":selected},allow_unicode=True,sort_keys=False),encoding="utf-8")
    STATS.write_text(json.dumps({"candidate_total":len(selected),"candidate_limit":sum(AU1RXX_LIMITS.values())+sum(EXTRA_LIMITS.values()),
                                 "source_stats":stats,"method":"dedupe + structural cleanup + obvious-bad filtering only","local_network_tests":False},
                                ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"candidate nodes: {len(selected)}")

if __name__=="__main__":
    main()
