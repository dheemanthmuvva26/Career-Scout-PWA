"""Push updated telegram_bot Code node to n8n."""
import json, os, time, urllib.request, urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('N8N_API_KEY', '')
BASE    = 'http://localhost:5678/api/v1'
WF_ID   = 'c2132b84-9330-4041-8c86-781701787eb4'
JS_FILE = Path(__file__).parent / 'n8n' / 'workflows' / 'telegram_bot_code.js'

NEW_JS  = JS_FILE.read_text(encoding='utf-8')

def n8n(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(f'{BASE}{path}', data=data, headers={
        'X-N8N-API-KEY': API_KEY, 'Content-Type': 'application/json',
    }, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'msg': e.read().decode()}

n8n('POST', f'/workflows/{WF_ID}/deactivate')
time.sleep(1)

wf = n8n('GET', f'/workflows/{WF_ID}')
for node in wf['nodes']:
    if node['type'] == 'n8n-nodes-base.code':
        node['parameters']['jsCode'] = NEW_JS
        print('Code node patched.')

n8n('PUT', f'/workflows/{WF_ID}', {
    'name': wf['name'], 'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': wf.get('settings', {}),
    'staticData': wf.get('staticData'),
})

time.sleep(1)
r = n8n('POST', f'/workflows/{WF_ID}/activate')
print('Active:', r.get('active'))
print('Done. Send /help or /start to the bot on Telegram.')
