import yaml
import subprocess
import time
import requests
import os


INPUT = "output/nikki.yaml"
OUTPUT = "output/nikki-speed.yaml"


API = "http://127.0.0.1:9090"

TEST_URL = "https://www.gstatic.com/generate_204"


with open(INPUT, encoding="utf8") as f:
    data = yaml.safe_load(f)


nodes = data["proxies"]


config = {

    "mixed-port": 7890,

    "external-controller":
        "127.0.0.1:9090",

    "secret": "",

    "mode": "rule",

    "log-level": "error",

    "proxies": nodes,


    "proxy-groups":[

        {
            "name":"TEST",
            "type":"url-test",
            "proxies":[
                n["name"]
                for n in nodes
            ],
            "url":TEST_URL,
            "interval":300
        }

    ],


    "rules":[

        "MATCH,TEST"

    ]

}



with open(
    "/tmp/mihomo-test.yaml",
    "w",
    encoding="utf8"
) as f:

    yaml.dump(
        config,
        f,
        allow_unicode=True,
        sort_keys=False
    )



p = subprocess.Popen(
    [
        "mihomo",
        "-f",
        "/tmp/mihomo-test.yaml"
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)


print("waiting mihomo start")

time.sleep(8)



result=[]


for node in nodes:

    name=node["name"]

    try:

        r=requests.get(

            f"{API}/proxies/{name}/delay",

            params={
                "timeout":5000,
                "url":TEST_URL
            }

        )


        delay=r.json().get("delay",999)


        print(
            name,
            delay
        )


        if delay and delay < 3000:

            node["delay"]=delay

            result.append(node)


    except Exception:

        pass



p.kill()



result.sort(
    key=lambda x:x.get("delay",999)
)



result=result[:30]



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
    "FINAL:",
    len(result)
)