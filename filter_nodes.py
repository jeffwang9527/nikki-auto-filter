# -*- coding: utf-8 -*-

import yaml
import os
import re


INPUT = "input/all.yaml"
OUTPUT = "output/nikki.yaml"


BAD_WORDS = re.compile(
    r"(expire|expired|traffic|test|测试|过期|剩余|流量|到期|公告|免费|试用)",
    re.I
)


TYPE_SCORE = {
    "hysteria2": 20,
    "vless": 15,
    "trojan": 12,
    "vmess": 5,
    "ss": 3
}


def score(node):

    s = 50

    name = str(node.get("name",""))
    server = str(node.get("server",""))

    text = name + " " + server


    t = node.get("type","")

    s += TYPE_SCORE.get(t,0)


    if node.get("tls"):
        s += 5

    if node.get("udp"):
        s += 3


    if BAD_WORDS.search(text):
        s -= 100


    return s



def region(name):

    name = str(name).lower()

    keywords = {
        "JP":[
            "jp",
            "japan",
            "tokyo",
            "osaka",
            "日本",
            "东京",
            "大阪"
        ],

        "HK":[
            "hk",
            "hong",
            "hongkong",
            "hong kong",
            "香港"
        ],

        "SG":[
            "sg",
            "singapore",
            "新加坡"
        ]
    }


    for r, words in keywords.items():

        for w in words:

            if w in name:
                return r


    return "OTHER"


with open(INPUT,encoding="utf8") as f:
    data=yaml.safe_load(f)


nodes=data.get("proxies",[])


groups={
    "JP":[],
    "HK":[],
    "SG":[],
    "OTHER":[]
}


for n in nodes:

    n["_score"] = score(n)

    text = (
        str(n.get("name",""))
        + " "
        + str(n.get("server",""))
    )

    groups[region(text)].append(n)



result=[]


limits={
    "JP":20,
    "HK":20,
    "SG":20,
    "OTHER":5
}


for r,items in groups.items():

    items.sort(
        key=lambda x:x["_score"],
        reverse=True
    )

    result.extend(
        items[:limits[r]]
    )


for n in result:
    n.pop("_score",None)



os.makedirs(
    "output",
    exist_ok=True
)


with open(
    OUTPUT,
    "w",
    encoding="utf8"
) as f:

    yaml.dump(
        {
            "proxies":result
        },
        f,
        allow_unicode=True,
        sort_keys=False
    )


print(
    "Total:",
    len(nodes),
    "Output:",
    len(result)
)