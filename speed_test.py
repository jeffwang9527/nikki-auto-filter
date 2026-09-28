import yaml
import subprocess
import time
import os


INPUT="output/nikki.yaml"
OUTPUT="output/nikki-speed.yaml"


with open(INPUT,encoding="utf8") as f:
    data=yaml.safe_load(f)


nodes=data["proxies"]

result=[]


for i,node in enumerate(nodes):

    name=node["name"]

    print(
        f"Testing {i+1}/{len(nodes)} {name}"
    )


    config={
        "mixed-port":7890,
        "mode":"rule",
        "log-level":"error",

        "proxies":[node],

        "proxy-groups":[
            {
                "name":"PROXY",
                "type":"select",
                "proxies":[name]
            }
        ],

        "rules":[
            "MATCH,PROXY"
        ]
    }


    with open(
        "/tmp/test.yaml",
        "w",
        encoding="utf8"
    ) as f:

        yaml.dump(
            config,
            f,
            allow_unicode=True
        )


    try:

        p=subprocess.Popen(
            [
                "mihomo",
                "-f",
                "/tmp/test.yaml"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


        time.sleep(5)


        r=subprocess.run(
            [
                "curl",
                "-x",
                "http://127.0.0.1:7890",
                "-m",
                "8",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{time_total}",
                "https://www.gstatic.com/generate_204"
            ],
            capture_output=True,
            text=True
        )


        p.kill()


        delay=float(r.stdout)


        print(
            "delay:",
            delay
        )


        if delay < 2.5:

            node["delay"]=delay

            result.append(node)



    except Exception as e:

        print(
            "failed",
            name
        )



result.sort(
    key=lambda x:x.get("delay",999)
)


with open(
    OUTPUT,
    "w",
    encoding="utf8"
) as f:

    yaml.dump(
        {
            "proxies":result[:15]
        },
        f,
        allow_unicode=True,
        sort_keys=False
    )


print(
    "Speed test result:",
    len(result)
)