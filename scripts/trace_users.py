oimport sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from main import app
from db import get_session
from models import User
from sqlmodel import select

def print_users(emails):
    with get_session() as s:
        for e in emails:
            u = s.exec(select(User).where(User.email==e)).first()
            print('DB user', e, '->', None if not u else (u.id, u.email, 'pwd_hash=', u.password_hash))

def run():
    client = TestClient(app)
    # signup
    r = client.post('/signup', json={"company_name":"Acme Ltd","country":"India","admin_name":"Alice","admin_email":"alice@acme.com"})
    print('signup', r.status_code, r.json())
    # admin login
    rt = client.post('/token', data={'username':'alice@acme.com','password':'admin'})
    print('admin token', rt.status_code)
    token = rt.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    print('\nBefore creating manager:')
    print_users(['alice@acme.com','bob@acme.com','eve@acme.com'])

    rm = client.post('/users', json={"name":"Manager Bob","email":"bob@acme.com","role":"manager","company_id":r.json()['company_id'], "password":"bobpass"}, headers=headers)
    print('\ncreate manager', rm.status_code, rm.json())
    print_users(['alice@acme.com','bob@acme.com','eve@acme.com'])

    re = client.post('/users', json={"name":"Employee Eve","email":"eve@acme.com","role":"employee","company_id":r.json()['company_id'], "manager_id": rm.json()['id']}, headers=headers)
    print('\ncreate employee', re.status_code, re.json())
    print_users(['alice@acme.com','bob@acme.com','eve@acme.com'])

    # try manager login
    rl = client.post('/token', data={'username':'bob@acme.com','password':'bobpass'})
    print('\nmanager login', rl.status_code, rl.text)

if __name__ == '__main__':
    run()
