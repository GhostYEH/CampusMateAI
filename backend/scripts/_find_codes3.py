import json
with open('data/universities.json', 'r', encoding='utf-8') as f:
    unis = json.load(f)
targets = ['深圳大学', '广州大学', '宁波大学', '汕头大学', '福州大学', '湖南大学',
           '复旦大学', '南开大学', '武汉大学', '华中师范大学', '东南大学']
for u in unis:
    if u['name'] in targets:
        print(f"{u['school_code']} | {u['name']} | {u.get('official_domain', '')}")