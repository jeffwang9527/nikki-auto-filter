# -*- coding: utf-8 -*-
import yaml
import os
import re

CONFIG = {
    "JP.yaml": {"hysteria2":10,"vless":10,"trojan":5},
    "HK.yaml": {"hysteria2":12,"vless":8,"trojan":5},
    "SG.yaml": {"vless":10,"hysteria2":6,"trojan":4}
}

BAD_WORDS = re.compile(
    r"(expire|expired|traffic|test|测试|过期|剩余|流量|到期|公告)",
    re.I
)

TYPE_SCORE = {
    "hysteria2":15,
    "vless":12,
    "trojan":10,
    "vmess":5,
    "ss":3
}

def load_nodes(file):
    with open(file,encoding="utf8") as f:
        return yaml.safe_load(f).get("proxies",[])

def score(node,region):
    s=50

    name=str(node.get("name",""))
    server=str(node.get("server",""))
    text=name+" "+server

    s += TYPE_SCORE.get(node.get("type",""),0)

    if region=="JP":
        s+=10
    elif region=="SG":
        s+=8
    else:
        s+=6

    if node.get("udp"):
        s+=3

    if node.get("tls"):
        s+=2

    if node.get("server"):
        s+=3

    if BAD_WORDS.search(text):
        s-=80

    return s

def process(src,plan):

    region=src.split(".")[0]

    nodes=load_nodes(src)

    scored=[]

    for n in nodes:
        n["_score"]=score(n,region)
        scored.append(n)


    result=[]


    for t,num in plan.items():

        group=[
            x for x in scored
            if x.get("type")==t
        ]

        group.sort(
            key=lambda x:x["_score"],
            reverse=True
        )

        result.extend(
            group[:num]
        )


    for n in result:
        n.pop("_score",None)


    os.makedirs(
        "output",
        exist_ok=True
    )


    out="output/"+region+"-filtered.yaml"


    with open(out,"w",encoding="utf8") as f:

        yaml.dump(
            {
                "proxies":result
            },
            f,
            allow_unicode=True,
            sort_keys=False
        )


    print(
        src,
        "原始:",
        len(nodes),
        "输出:",
        len(result)
    )



for file,plan in CONFIG.items():

    if os.path.exists(file):

        process(
            file,
            plan
        )

