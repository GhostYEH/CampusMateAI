import json
from itertools import groupby

data = json.load(open('data/edu_system_candidates.json', encoding='utf-8'))
cands = data['candidates']
unis = json.load(open('data/universities.json', encoding='utf-8'))
schools_with_url = set(c['school_name'] for c in cands if c.get('candidate_url'))
not_disc = [u for u in unis if u['name'] not in schools_with_url and u.get('level') == '本科']
print(f'Total undergrad without URL: {len(not_disc)}')
not_disc.sort(key=lambda x: (x.get('province', ''), x['name']))
for p, group in groupby(not_disc, key=lambda x: x.get('province', '')):
    gs = list(group)
    print(f'  {p}: {len(gs)} schools')
    for g in gs[:3]:
        domain = g.get('official_domain') or g.get('official_website', '').replace('http://', '').replace('https://', '').split('/')[0] if g.get('official_website') else ''
        print(f'    - {g["name"]} ({g.get("school_code","")}) domain={domain}')