from pathlib import Path
import yaml


base = Path("output")

config = {
    "mixed-port": 7890,
    "allow-lan": False,
    "mode": "rule",
    "log-level": "info",
    "ipv6": False,

    "proxy-providers": {
        "NIKKI-GENERAL": {
            "type": "http",
            "url": "https://cdn.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@main/output/nikki-general.yaml",
            "path": "./providers/nikki-general.yaml",
            "interval": 14400,
            "health-check": {
                "enable": True,
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300
            }
        },

        "NIKKI-GPT": {
            "type": "http",
            "url": "https://cdn.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@main/output/nikki-chatgpt.yaml",
            "path": "./providers/nikki-chatgpt.yaml",
            "interval": 14400,
            "health-check": {
                "enable": True,
                "url": "https://chatgpt.com/robots.txt",
                "interval": 300
            }
        }
    },

    "proxy-groups": [
        {
            "name": "NIKKI-普通池",
            "type": "url-test",
            "use": ["NIKKI-GENERAL"],
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "tolerance": 50
        },

        {
            "name": "NIKKI-GPT专用池",
            "type": "url-test",
            "use": ["NIKKI-GPT"],
            "url": "https://chatgpt.com/robots.txt",
            "interval": 300,
            "tolerance": 50
        }
    ],

    "rules": [
        "DOMAIN-SUFFIX,chatgpt.com,NIKKI-GPT专用池",
        "DOMAIN-SUFFIX,openai.com,NIKKI-GPT专用池",
        "DOMAIN-SUFFIX,oaistatic.com,NIKKI-GPT专用池",
        "DOMAIN-SUFFIX,oaiusercontent.com,NIKKI-GPT专用池",

        "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
        "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
        "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",

        "GEOSITE,cn,DIRECT",
        "GEOIP,CN,DIRECT",

        "MATCH,NIKKI-普通池"
    ]
}


with open(base / "nikki-mobile.yaml", "w", encoding="utf-8") as f:
    yaml.dump(
        config,
        f,
        allow_unicode=True,
        sort_keys=False
    )

print("generated output/nikki-mobile.yaml")