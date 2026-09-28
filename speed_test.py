import yaml
import requests
import time


FILE="output/nikki.yaml"


TEST_URL="https://www.gstatic.com/generate_204"


with open(FILE,encoding="utf8") as f:
    data=yaml.safe_load(f)


nodes=data["proxies"]


result=[]


for n in nodes:

    server=n.get("server")

    port=n.get("port")


    if not server:
        continue


    print("testing:",n["name"])


    start=time.time()

    try:

        r=requests.get(
            TEST_URL,
            timeout=5
        )

        delay=round(
            (time.time()-start)*1000
        )


        n["_delay"]=delay

        result.append(n)


        print(
            delay,
            "ms"
        )


    except:

        print("timeout")



result.sort(
    key=lambda x:x.get("_delay",9999)
)


for n in result:

    n.pop("_delay",None)



with open(
    "output/nikki_speed.yaml",
    "w",
    encoding="utf8"
) as f:

    yaml.safe_dump(
        {
            "proxies":result
        },
        f,
        allow_unicode=True,
        sort_keys=False
    )


print(
    "saved",
    len(result)
)