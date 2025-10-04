import os, sys
from pathlib import Path
# Add project root to sys.path so imports like 'from main import app' work when this script
# is executed from the scripts/ directory.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

print('POST /signup')
r = client.post('/signup', json={"company_name":"Acme Run","country":"India","admin_name":"Alice","admin_email":"alice@acme.run"})
print(r.status_code, r.json())

print('POST /token')
r2 = client.post('/token', data={'username':'alice@acme.run','password':'admin'})
print(r2.status_code, r2.json())
if r2.status_code==200:
    token = r2.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    print('POST /users (create manager)')
    ru = client.post('/users', json={"name":"Manager Bob","email":"bob@acme.run","role":"manager","company_id": r.json()['company_id']}, headers=headers)
    print(ru.status_code, ru.json())
    print('POST /users (create employee)')
    re = client.post('/users', json={"name":"Employee Eve","email":"eve@acme.run","role":"employee","company_id": r.json()['company_id'], "manager_id": ru.json()['id']}, headers=headers)
    print(re.status_code, re.json())
    print('POST /expenses (submit by Eve)')
    rex = client.post('/expenses', json={"submitter_id": re.json()['id'], "amount": 50.0, "currency": "INR", "category": "meals", "description": "Test lunch"}, headers=headers)
    print(rex.status_code, rex.json())
