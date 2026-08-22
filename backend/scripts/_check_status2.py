import json
from collections import Counter
with open('data/edu_system_candidates.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
urls = [r for r in d['candidates'] if r.get('candidate_url')]
print(f'Total: {len(d["candidates"])}, with URL: {len(urls)}, schools: {len(set(r["school_name"] for r in urls))}')
c = Counter(r.get('verification_status', 'UNKNOWN') for r in urls)
print('Status:', dict(c))