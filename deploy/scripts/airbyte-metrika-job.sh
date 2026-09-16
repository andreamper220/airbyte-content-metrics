#!/bin/bash
set -eu
python3 <<'PY'
import json, re, subprocess, urllib.request
HOST='content.netvolk.online'; BASE='http://127.0.0.1:18091/api/v1'
CONN='eae89902-de9e-4482-b3f2-4118f21d77d0'
raw=subprocess.check_output(['abctl','local','credentials'], stderr=subprocess.STDOUT, text=True)
clean=re.sub(r'\x1b\[[0-9;]*m','',raw); cid=csec=''
for line in clean.splitlines():
    if 'Client-Id:' in line: cid=line.split('Client-Id:',1)[1].strip()
    if 'Client-Secret:' in line: csec=line.split('Client-Secret:',1)[1].strip()
req=urllib.request.Request(f'{BASE}/applications/token', data=json.dumps({'client_id':cid,'client_secret':csec}).encode(), headers={'Content-Type':'application/json','Host':HOST}, method='POST')
with urllib.request.urlopen(req) as r: tok=json.loads(r.read())['access_token']
def call(path,p):
    req=urllib.request.Request(f'{BASE}{path}', data=json.dumps(p).encode(), headers={'Content-Type':'application/json','Host':HOST,'Authorization':f'Bearer {tok}'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
jobs=call('/jobs/list', {'configTypes':['sync'], 'configId': CONN, 'limit': 5})
for j in jobs.get('jobs',[]):
    print(j.get('id'), j.get('status'), j.get('createdAt'))
    att=call('/jobs/get', {'id': j['id']})
    for a in att.get('attempts',[]):
        print('  attempt', a.get('status'), (a.get('failureSummary') or {}).get('failureMessage','')[:200])
PY
