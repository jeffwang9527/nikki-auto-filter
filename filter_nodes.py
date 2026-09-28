import os
import yaml
import glob
import re


OUTPUT = "output/nikki.yaml"

REGIONS = {
    "JP": 20,
    "HK": 20,
    "SG": 10,
}


BAD_WORDS = re.compile(
    r"(expire|expired|traffic|test|free|trial|鍓╀綑|娴侀噺|鍒版湡|瀹樼綉|鍏嶈垂)",
    re.I
)


TYPE_SCORE = {
    "vless": 30,
    "trojan": 20,
    "hysteria2": 20,
    "vmess": 10,
    "ss": 5
}


def node_key(node):

    if node.get("reality-opts"):

        return (
            str(node.get("server","")),
            str(node.get("uuid","")),
            str(node.get("reality-opts",{}).get("public-key",""))
        )

    return (
        str(node.get("server","")),
        str(node.get("port","")),
        str(node.get("type",""))
    )


def score(node, region):

    s = 50

    # Reality / Vision 浼樺厛
    if node.get("reality-opts"):
        s += 15

    if node.get("flow") == "xtls-rprx-vision":
        s += 10

    if node.get("network") == "tcp" and node.get("reality-opts"):
        s += 3

    name = str(node.get("name", ""))

    ntype = str(node.get("type", "")).lower()

    s += TYPE_SCORE.get(ntype, 0)

    # 鍦板尯鏉ユ簮鏉冮噸
    s += REGIONS.get(region, 0)

    if node.get("tls"):
        s += 5

    if node.get("udp"):
        s += 3

    # 璐ㄩ噺杩囨护
    if node.get("reality-opts"):
        s += 5

    if not node.get("servername"):
        s -= 20

    if str(node.get("type","")).lower() == "trojan":
        s -= 10

    text = (
        name +
        " " +
        str(node.get("server", ""))
    )

    if BAD_WORDS.search(text):
        s -= 50

    return s



def load_region(region):

    result = []
    seen = set()

    files = glob.glob(
        f"input/{region}/*.yaml"
    )

    print(
        f"{region} source files:",
        len(files)
    )

    for file in files:

        try:

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                data = yaml.safe_load(f)


            if not data:
                continue


            proxies = data.get(
                "proxies",
                []
            )


            for node in proxies:

                if not isinstance(node, dict):
                    continue


                if not node.get("server"):
                    continue


                key = node_key(node)

                if key in seen:
                    continue

                seen.add(key)


                node["_region"] = region
                node["_score"] = score(
                    node,
                    region
                )


                result.append(node)


        except Exception as e:

            print(
                "skip",
                file,
                e
            )


        result.sort(
            key=lambda x:(
                ["JP","HK","SG"].index(x.get("_region","SG")),
                -x["_score"]
            )
        )

    print(
        region,
        "clean:",
        len(result)
    )

    return result



def main():

    output = []


    limits = {
        "JP":20,
        "HK":20,
        "SG":10
    }


    for region in REGIONS:

        nodes = load_region(region)


        selected = nodes[
            :limits[region]
        ]


        print(
            region,
            "selected:",
            len(selected)
        )

        for n in selected:
            n["name"] = f"{region} | {n.get('name','unknown')}"

        output.extend(selected)


    os.makedirs(
        "output",
        exist_ok=True
    )


    clean=[]


    for n in output:

        n.pop(
            "_score",
            None
        )

        n.pop(
            "_region",
            None
        )

        clean.append(n)



    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:

        yaml.safe_dump(
    {
        "proxies": clean,
        "proxy-groups": [
            {
                "name": "[JP] JP Auto",
                "type": "url-test",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [
                    n["name"] for n in clean
                    if n["name"].startswith("JP |")
                ]
            },
            {
                "name": "[HK] HK Auto",
                "type": "url-test",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [
                    n["name"] for n in clean
                    if n["name"].startswith("HK |")
                ]
            },
            {
                "name": "[SG] SG Auto",
                "type": "url-test",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [
                    n["name"] for n in clean
                    if n["name"].startswith("SG |")
                ]
            },
            {
                "name": "[ALL] Auto",
                "type": "fallback",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [
                    "[JP] JP Auto",
                    "[HK] HK Auto",
                    "[SG] SG Auto"
                ]
            }
        ]
    },
    f,
    allow_unicode=True,
    sort_keys=False
)


    print(
        "Total output:",
        len(clean)
    )

    print(
        "Saved:",
        OUTPUT
    )



if __name__=="__main__":
    main()

