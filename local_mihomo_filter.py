#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,shutil,socket,subprocess,tempfile,time,urllib.parse
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from statistics import median
from typing import Any
import requests,yaml

GENERAL_TESTS=[("gstatic","https://www.gstatic.com/generate_204","204",6500),
                ("cloudflare","https://www.cloudflare.com/cdn-cgi/trace","200-299",6500)]
OPENAI_TESTS=[("chatgpt_edge","https://chatgpt.com/robots.txt","200-499",8500),
              ("auth_edge","https://auth.openai.com/","200-499",8500),
              ("openai_api","https://api.openai.com/v1/models","401",8500)]
SUCCESS_TTL=6*3600
FAIL_COOLDOWN=6*3600
FAIL_EJECT_STREAK=3
MAX_SAME_SERVER=2

def scalar(v:Any)->str:return "" if v is None else str(v)

def node_key(n):
    r=n.get("reality-opts") or {};w=n.get("ws-opts") or {};g=n.get("grpc-opts") or {}
    payload={"type":scalar(n.get("type")).lower(),"server":scalar(n.get("server")).lower(),"port":scalar(n.get("port")),
             "uuid":scalar(n.get("uuid")),"password":scalar(n.get("password")),"username":scalar(n.get("username")),
             "cipher":scalar(n.get("cipher")),"servername":scalar(n.get("servername") or n.get("sni")),
             "network":scalar(n.get("network")).lower(),"path":scalar(n.get("path") or w.get("path")),"flow":scalar(n.get("flow")),
             "grpc_service_name":scalar(n.get("service-name") or g.get("grpc-service-name")),
             "reality_public_key":scalar(r.get("public-key")),"reality_short_id":scalar(r.get("short-id"))}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def server_key(n):return f"{scalar(n.get('server')).lower()}:{scalar(n.get('port'))}"

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0));return int(s.getsockname()[1])

def load_nodes(path):
    d=yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict) or not isinstance(d.get("proxies"),list):raise ValueError(f"Invalid candidate YAML: {path}")
    return[n for n in d["proxies"] if isinstance(n,dict)]

def load_cache(path):
    p=Path(path)
    if not p.exists():return{}
    try:
        d=json.loads(p.read_text(encoding="utf-8"));return d if isinstance(d,dict) else{}
    except Exception as e:
        print("[WARN] cache ignored:",e);return{}

def save_cache(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");tmp.replace(p)

def due(state,kind,full):
    last=int(state.get(f"last_{kind}_test",0) or 0)
    if full or not last:return True
    return time.time()-last>=SUCCESS_TTL if state.get(f"{kind}_ok") else time.time()-last>=FAIL_COOLDOWN

class MihomoRunner:
    def __init__(self,binary,nodes):
        self.binary=Path(binary);self.nodes=nodes;self.root=Path(tempfile.mkdtemp(prefix="nikki-local-mihomo-"))
        self.config=self.root/"config.yaml";self.log=self.root/"mihomo.log";self.port=free_port();self.secret=hashlib.sha256(os.urandom(32)).hexdigest()
        self.base=f"http://127.0.0.1:{self.port}";self.proc=None

    def start(self):
        proxies=[];names=set()
        for i,raw in enumerate(self.nodes):
            n=dict(raw);name=scalar(n.get("name")).strip() or f"node-{i:04d}"
            if name in names:name=f"{name} [{i}]"
            names.add(name);n["name"]=name;n["ip-version"]="ipv4";proxies.append(n)
        cfg={"mode":"rule","log-level":"warning","ipv6":False,"unified-delay":True,"tcp-concurrent":True,
             "allow-lan":False,"external-controller":f"127.0.0.1:{self.port}","secret":self.secret,"proxies":proxies}
        self.config.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding="utf-8")
        with self.log.open("w",encoding="utf-8") as fh:
            self.proc=subprocess.Popen([str(self.binary),"-f",str(self.config),"-d",str(self.root)],stdout=fh,stderr=subprocess.STDOUT,text=True,cwd=str(self.root))
        headers={"Authorization":f"Bearer {self.secret}"};end=time.time()+20;last=""
        while time.time()<end:
            if self.proc.poll() is not None:raise RuntimeError(self.log.read_text(encoding="utf-8",errors="ignore")[-6000:])
            try:
                r=requests.get(f"{self.base}/version",headers=headers,timeout=1.5)
                if r.ok:return
                last=f"HTTP {r.status_code}"
            except requests.RequestException as e:last=str(e)
            time.sleep(.25)
        raise TimeoutError(f"mihomo API not ready: {last}")

    def delay(self,name,url,timeout_ms,expected):
        encoded=urllib.parse.quote(name,safe="");headers={"Authorization":f"Bearer {self.secret}"}
        try:
            r=requests.get(f"{self.base}/proxies/{encoded}/delay",params={"url":url,"timeout":timeout_ms,"expected":expected},
                           headers=headers,timeout=(2,timeout_ms/1000+2))
            if r.status_code!=200:return None
            d=r.json().get("delay");return int(d) if isinstance(d,int) and d>0 else None
        except (requests.RequestException,ValueError,TypeError):return None

    def close(self):
        try:
            if self.proc is not None:self.proc.terminate();self.proc.wait(timeout=5)
        except Exception:
            try:
                if self.proc is not None:self.proc.kill()
            except Exception:pass
        shutil.rmtree(self.root,ignore_errors=True)

def run_probe(runner,node,previous,full):
    state=dict(previous);state["name"]=scalar(node.get("name"))
    if due(state,"general",full):
        delays={};ok=True
        for label,url,expected,timeout in GENERAL_TESTS:
            d=runner.delay(state["name"],url,timeout,expected)
            if d is None:ok=False;break
            delays[label]=d
        now=int(time.time());state["last_general_test"]=now;state["general_ok"]=ok;state["general_delays"]=delays
        if ok:
            state["general_median"]=int(median(delays.values()));state["general_consecutive_success"]=int(state.get("general_consecutive_success",0))+1
            state["general_consecutive_fail"]=0;state["general_last_success"]=now;state["general_last_success_median"]=state["general_median"]
        else:
            state["general_median"]=None;state["general_consecutive_fail"]=int(state.get("general_consecutive_fail",0))+1;state["general_consecutive_success"]=0
    if due(state,"openai",full):
        delays={};ok=True
        for label,url,expected,timeout in OPENAI_TESTS:
            d=runner.delay(state["name"],url,timeout,expected)
            if d is None:ok=False;break
            delays[label]=d
        now=int(time.time());state["last_openai_test"]=now;state["openai_ok"]=ok;state["openai_delays"]=delays
        if ok:
            state["openai_median"]=int(median(delays.values()));state["openai_consecutive_success"]=int(state.get("openai_consecutive_success",0))+1
            state["openai_consecutive_fail"]=0;state["openai_last_success"]=now;state["openai_last_success_median"]=state["openai_median"]
        else:
            state["openai_median"]=None;state["openai_consecutive_fail"]=int(state.get("openai_consecutive_fail",0))+1;state["openai_consecutive_success"]=0
    state["last_run"]=int(time.time());return state

def eligible(state,kind):
    if state.get(f"{kind}_ok"):return True,False
    grace=int(state.get(f"{kind}_consecutive_fail",0))<FAIL_EJECT_STREAK and int(state.get(f"{kind}_last_success",0))>0
    return grace,grace

def pick(items,limit,metric,excluded=None):
    excluded=excluded or set()
    def rank(item):
        n,st,grace=item;delay=st.get(metric)
        if delay is None:delay=st.get("general_last_success_median" if metric=="general_median" else "openai_last_success_median",999999)
        return (1 if grace else 0,float(delay or 999999),scalar(n.get("name")))
    chosen=[];servers={}
    for n,st,grace in sorted(items,key=rank):
        k=node_key(n);sk=server_key(n)
        if k in excluded or servers.get(sk,0)>=MAX_SAME_SERVER:continue
        chosen.append((n,st,grace));excluded.add(k);servers[sk]=servers.get(sk,0)+1
        if len(chosen)>=limit:break
    return chosen

def write_yaml(path,nodes):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump({"proxies":nodes},allow_unicode=True,sort_keys=False),encoding="utf-8");tmp.replace(p)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mihomo",required=True);ap.add_argument("--candidate",default="output/candidates.yaml");ap.add_argument("--cache",default="cache/node-cache.json")
    ap.add_argument("--report",default="output/local-test-report.json");ap.add_argument("--general-out",default="output/nikki-general.yaml")
    ap.add_argument("--chatgpt-out",default="output/nikki-chatgpt.yaml");ap.add_argument("--union-out",default="output/nikki.yaml")
    ap.add_argument("--general-limit",type=int,default=12);ap.add_argument("--chatgpt-limit",type=int,default=8);ap.add_argument("--concurrency",type=int,default=6)
    ap.add_argument("--full",action="store_true");a=ap.parse_args()
    candidates=load_nodes(Path(a.candidate));cache=load_cache(Path(a.cache))
    unique=[];seen=set()
    for n in candidates:
        k=node_key(n)
        if k not in seen:seen.add(k);unique.append(n)
    todo=[n for n in unique if due(cache.get(node_key(n),{}),"general",a.full) or due(cache.get(node_key(n),{}),"openai",a.full)]
    print(f"[local] candidates={len(unique)} to_test={len(todo)} cache_reused={len(unique)-len(todo)} concurrency={a.concurrency}")
    results=dict(cache)
    if todo:
        runner=MihomoRunner(a.mihomo,unique);runner.start()
        try:
            with ThreadPoolExecutor(max_workers=max(1,a.concurrency)) as pool:
                fs={pool.submit(run_probe,runner,n,cache.get(node_key(n),{}),a.full):n for n in todo}
                for i,f in enumerate(as_completed(fs),1):
                    n=fs[f];k=node_key(n)
                    try:results[k]=f.result()
                    except Exception as e:results[k]={**cache.get(k,{}),"name":scalar(n.get("name")),"general_ok":False,"openai_ok":False,"error":str(e),"last_run":int(time.time())}
                    print(f"[local] {i}/{len(todo)} {n.get('name')}")
        finally:runner.close()
    save_cache(Path(a.cache),results)
    general=[];openai=[]
    for n in unique:
        st=results.get(node_key(n),{});ok,g=eligible(st,"general")
        if ok:general.append((n,st,g))
        ok,g=eligible(st,"openai")
        if ok:openai.append((n,st,g))
    chat_pick=pick(openai,a.chatgpt_limit,"openai_median");excluded={node_key(n) for n,_,_ in chat_pick}
    gen_pick=pick(general,a.general_limit,"general_median",excluded)
    gen=[{**n,"name":f"GEN | {scalar(n.get('name'))}"} for n,_,_ in gen_pick]
    gpt=[{**n,"name":f"GPT | {scalar(n.get('name'))}"} for n,_,_ in chat_pick]
    write_yaml(a.general_out,gen);write_yaml(a.chatgpt_out,gpt);write_yaml(a.union_out,gpt+gen)
    report={"timestamp":int(time.time()),"candidate_count":len(unique),"tested_now":len(todo),"cache_reused":len(unique)-len(todo),
            "general_eligible":len(general),"openai_edge_eligible":len(openai),"selected_general":len(gen),"selected_chatgpt":len(gpt),"selected_total":len(gen)+len(gpt),
            "policy":{"general_limit":a.general_limit,"chatgpt_limit":a.chatgpt_limit,"concurrency":a.concurrency,"success_retest_hours":SUCCESS_TTL/3600,
                      "failure_cooldown_hours":FAIL_COOLDOWN/3600,"failure_eject_streak":FAIL_EJECT_STREAK,"max_same_server":MAX_SAME_SERVER},
            "selected":{"general":[{"name":scalar(n.get("name")),"delay_ms":st.get("general_median") or st.get("general_last_success_median"),"grace":g} for n,st,g in gen_pick],
                        "chatgpt":[{"name":scalar(n.get("name")),"delay_ms":st.get("openai_median") or st.get("openai_last_success_median"),"grace":g} for n,st,g in chat_pick]},
            "note":"OpenAI/ChatGPT result is transport/edge reachability from this Windows network; it does not guarantee login, websocket, streaming, or long-term stability."}
    Path(a.report).parent.mkdir(parents=True,exist_ok=True);Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("candidate_count","tested_now","cache_reused","general_eligible","openai_edge_eligible","selected_general","selected_chatgpt","selected_total")},ensure_ascii=False))
if __name__=="__main__":main()
