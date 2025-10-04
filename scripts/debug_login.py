import sys
from pathlib import Path
# ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app

def run():
    client = TestClient(app)

    r = client.post('/signup', json={"company_name":"DbgCo","country":"India","admin_name":"A","admin_email":"a@dbg"})
    print('signup', r.status_code, r.json())

    rt = client.post('/token', data={'username':'a@dbg','password':'admin'})
    print('admin token', rt.status_code, rt.json())
    token = rt.json().get('access_token')
    headers = {'Authorization': f'Bearer {token}'}

    ru = client.post('/users', json={"name":"Mgr","email":"mgr@dbg","role":"manager","company_id": r.json()['company_id'], "password":"mgrpass"}, headers=headers)
    print('create manager', ru.status_code, ru.json())

    # attempt login as manager
    rl = client.post('/token', data={'username':'mgr@dbg','password':'mgrpass'})
    print('manager login', rl.status_code, rl.text)

if __name__ == '__main__':
    run()
