import json

with open("data/universities.json", "r", encoding="utf-8") as f:
    unis = json.load(f)

targets = ["贵州大学", "山西大学", "广西大学"]
for uni in unis:
    if uni["name"] in targets:
        print(f"{uni['name']} | {uni.get('school_code', 'N/A')} | {uni.get('province', 'N/A')}")
