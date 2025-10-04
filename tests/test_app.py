from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_signup_and_flow():
    # signup
    resp = client.post('/signup', json={"company_name":"Acme Ltd","country":"India","admin_name":"Alice","admin_email":"alice@acme.com"})
    assert resp.status_code == 200
    data = resp.json()
    company_id = data['company_id']
    admin_id = data['admin_id']
    # login as admin (default password 'admin') to get token
    resp = client.post('/token', data={"username": "alice@acme.com", "password": "admin"})
    assert resp.status_code == 200
    token = resp.json()['access_token']
    headers = {"Authorization": f"Bearer {token}"}

    # admin can create a manager
    resp = client.post('/users', json={"name":"Manager Bob","email":"bob@acme.com","role":"manager","company_id":company_id, "password": "bobpass"}, headers=headers)
    assert resp.status_code == 200
    bob = resp.json()
    # create an employee
    resp = client.post('/users', json={"name":"Employee Eve","email":"eve@acme.com","role":"employee","company_id":company_id, "manager_id": bob['id']}, headers=headers)
    assert resp.status_code == 200
    eve = resp.json()
    # login as manager and attempt to create user -> should be forbidden
    resp = client.post('/token', data={"username": "bob@acme.com", "password": "bobpass"})
    assert resp.status_code == 200
    manager_token = resp.json()['access_token']
    mgr_headers = {"Authorization": f"Bearer {manager_token}"}
    resp = client.post('/users', json={"name":"Bad User","email":"bad@acme.com","role":"employee","company_id":company_id}, headers=mgr_headers)
    assert resp.status_code == 403
    # submit expense by Eve
    resp = client.post('/expenses', json={"submitter_id": eve['id'], "amount": 100.0, "currency": "INR", "category":"meals", "description":"Team lunch"}, headers=headers)
    assert resp.status_code == 200
    exp = resp.json()
    eid = exp['id']
    # manager sees pending
    resp = client.get(f'/approvals/user/{bob["id"]}/pending')
    assert resp.status_code == 200
    pending = resp.json()
    assert len(pending) >= 1
    step_id = pending[0]['step_id']
    # manager approves (must be authenticated)
    resp = client.post(f'/approvals/{eid}/decision', json={"approver_id": bob['id'], "approved": True, "comment": "ok"}, headers=mgr_headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res['status'] in ('pending', 'approved')
