from pathlib import Path

p = Path("filter_nodes.py")

s = p.read_text(encoding="utf-8")


if "def deduplicate(nodes):" not in s:

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

    s = s.replace(
        "def region(name):",
        code + "def region(name):"
    )


if "result=deduplicate(result)" not in s:

    s = s.replace(
        'for n in result:\n    n.pop("_score",None)',
        'result=deduplicate(result)\n\n\nfor n in result:\n    n.pop("_score",None)'
    )


p.write_text(s, encoding="utf-8")

print("done")