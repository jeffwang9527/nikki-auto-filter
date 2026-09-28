from pathlib import Path

p = Path("filter_nodes.py")

s = p.read_text(encoding="utf-8")


code = """

def deduplicate(nodes):

    seen=set()
    result=[]

    for n in nodes:

        key=(
            n.get("type",""),
            n.get("server",""),
            str(n.get("port","")),
            n.get("uuid",""),
            n.get("password","")
        )

        if key not in seen:
            seen.add(key)
            result.append(n)

    return result


"""


if "def deduplicate(nodes):" not in s:
    s=s.replace(
        "def region(name):",
        code+"def region(name):"
    )


if "result=deduplicate(result)" not in s:
    s=s.replace(
        "for n in result:",
        "result=deduplicate(result)\n\n\nfor n in result:"
    )


p.write_text(s,encoding="utf-8")

print("finished")