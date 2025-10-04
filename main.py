import os
from fastapi import FastAPI, HTTPException, Body, Depends
from typing import List, Optional
from sqlmodel import select
from db import init_db, get_session
from models import Company, User, Expense, ApprovalStep, ApprovalDecision, ApprovalRule
from auth import create_access_token, get_password_hash, verify_password, get_current_user
from fastapi.security import OAuth2PasswordRequestForm
from datetime import date
import requests
from fastapi import UploadFile, File

app = FastAPI()


@app.get("/")
def root():
    """Health endpoint - returns a small status JSON and link to API docs."""
    return {"status": "ok", "service": "expense-app", "docs": "/docs"}

USE_EXTERNAL = os.environ.get("USE_EXTERNAL") == "1"

# Helpers for country/currency and exchange rates. Mocked when USE_EXTERNAL is False.
def get_currency_for_country(country_name: str) -> str:
    if not USE_EXTERNAL:
        # simple mock: if name contains 'United' -> USD, if 'India' -> INR else EUR
        if 'India' in country_name:
            return 'INR'
        if 'United' in country_name:
            return 'USD'
        return 'EUR'
    resp = requests.get('https://restcountries.com/v3.1/all?fields=name,currencies')
    resp.raise_for_status()
    data = resp.json()
    for item in data:
        name = item.get('name', {}).get('common')
        if not name:
            continue
        if name.lower() == country_name.lower():
            currencies = item.get('currencies', {})
            if currencies:
                return list(currencies.keys())[0]
    # fallback
    return 'USD'

def get_exchange_rates(base: str) -> dict:
    if not USE_EXTERNAL:
        # mock rates
        return {base: 1.0, 'USD': 1.0, 'EUR': 0.9, 'INR': 82.0}
    url = f'https://api.exchangerate-api.com/v4/latest/{base}'
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get('rates', {})

@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("startup")
def seed_default():
    """If no company exists, create a sample company and an admin with password 'admin'.
    This makes it easy to run the app and have an admin user ready: email=admin@sample, password=admin
    """
    from sqlmodel import select
    from models import Company, User, ApprovalRule
    with get_session() as s:
        any_company = s.exec(select(Company)).first()
        if not any_company:
            company = Company(name="SampleCo", country="India", currency=get_currency_for_country("India"))
            s.add(company)
            s.commit()
            s.refresh(company)
            admin = User(name="Administrator", email="admin@sample", role="admin", company_id=company.id, password_hash=get_password_hash('admin'))
            s.add(admin)
            s.commit()
            # default approval rule
            rule = ApprovalRule(company_id=company.id, percentage_threshold=50, special_approver_ids='')
            s.add(rule)
            s.commit()


@app.get('/')
def root():
    return {"status": "ok", "message": "Expense app running", "sample_admin": {"email": "admin@sample", "password": "admin"}}

# ensure tables exist when importing the module for tests
init_db()

@app.post('/signup')
def signup(company_name: str = Body(...), country: str = Body(...), admin_name: str = Body(...), admin_email: str = Body(...)):
    currency = get_currency_for_country(country)
    with get_session() as s:
        company = Company(name=company_name, country=country, currency=currency)
        s.add(company)
        s.commit()
        s.refresh(company)
        # default admin password = 'admin' in prototype (hashed)
        admin = User(name=admin_name, email=admin_email, role='admin', company_id=company.id, password_hash=get_password_hash('admin'))
        s.add(admin)
        s.commit()
        s.refresh(admin)
        # default approval rule: 50% threshold
        rule = ApprovalRule(company_id=company.id, percentage_threshold=50, special_approver_ids='')
        s.add(rule)
        s.commit()
        # capture ids to return after session closes
        company_id = company.id
        admin_id = admin.id
    return {"company_id": company_id, "admin_id": admin_id, "currency": currency}

@app.post('/users')
def create_user(name: str = Body(...), email: str = Body(...), role: str = Body('employee'), company_id: int = Body(...), manager_id: Optional[int] = Body(None), password: Optional[str] = Body(None), current=Depends(get_current_user)):
    # require admin role to create users
    if not current or current.get('role') != 'admin':
        raise HTTPException(status_code=403, detail='admin role required')
    with get_session() as s:
        # if a user with this email already exists, update it instead of creating duplicate
        existing = s.exec(select(User).where(User.email == email)).first()
        if existing:
            existing.name = name
            existing.role = role
            existing.company_id = company_id
            existing.manager_id = manager_id
            if password:
                existing.password_hash = get_password_hash(password)
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing

        pwd_hash = None
        if password:
            pwd_hash = get_password_hash(password)
        user = User(name=name, email=email, role=role, company_id=company_id, manager_id=manager_id, password_hash=pwd_hash)
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


@app.post('/token')
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_session() as s:
        user = s.exec(select(User).where(User.email == form_data.username)).first()
        if not user or not user.password_hash:
            raise HTTPException(status_code=400, detail='Incorrect username or password')
        if not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=400, detail='Incorrect username or password')
        token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role})
        return {"access_token": token, "token_type": "bearer"}

@app.post('/expenses')
def submit_expense(submitter_id: int = Body(...), amount: float = Body(...), currency: str = Body(...), category: Optional[str] = Body(None), description: Optional[str] = Body(None), date_: Optional[str] = Body(None), approver_ids: Optional[List[int]] = Body(None), current=Depends(get_current_user)):
    if date_:
        d = date.fromisoformat(date_)
    else:
        d = date.today()
    with get_session() as s:
        submitter = s.get(User, submitter_id)
        if not submitter:
            raise HTTPException(status_code=404, detail='submitter not found')
        company = s.get(Company, submitter.company_id)
        if not company:
            raise HTTPException(status_code=404, detail='company not found')
        rates = get_exchange_rates(currency)
        company_rates = get_exchange_rates(company.currency)
        # naive conversion: convert amount -> USD -> company currency via rates dict
        # if rates missing, fallback 1:1
        try:
            rate_to_base = rates.get(company.currency) or 1.0
        except Exception:
            rate_to_base = 1.0
        # better approach: get rates with base currency provided by external API; here we just mock
        amount_company = amount
        if currency != company.currency:
            # If we have rates mapping with company.currency key, use it
            rates_for_currency = get_exchange_rates(currency)
            comp_rate = rates_for_currency.get(company.currency)
            if comp_rate:
                amount_company = amount * comp_rate
        expense = Expense(submitter_id=submitter_id, company_id=company.id, amount=amount, currency=currency, amount_company_currency=amount_company, category=category, description=description, date=d)
        s.add(expense)
        s.commit()
        s.refresh(expense)
        # determine approval steps: if approver_ids provided, use them, else default to manager chain
        steps = []
        if approver_ids:
            seq = 1
            for aid in approver_ids:
                step = ApprovalStep(expense_id=expense.id, approver_id=aid, sequence=seq)
                s.add(step)
                seq += 1
        else:
            # default: manager -> company admin(s)
            seq = 1
            if submitter.manager_id:
                step = ApprovalStep(expense_id=expense.id, approver_id=submitter.manager_id, sequence=seq)
                s.add(step)
                seq += 1
            # add all admins in company
            admins = s.exec(select(User).where(User.company_id == company.id).where(User.role == 'admin')).all()
            for a in admins:
                step = ApprovalStep(expense_id=expense.id, approver_id=a.id, sequence=seq)
                s.add(step)
                seq += 1
        s.commit()
        # capture fields while attached to session
        result = {
            "id": expense.id,
            "submitter_id": expense.submitter_id,
            "company_id": expense.company_id,
            "amount": expense.amount,
            "currency": expense.currency,
            "amount_company_currency": expense.amount_company_currency,
            "category": expense.category,
            "description": expense.description,
            "date": expense.date.isoformat() if expense.date else None,
            "status": expense.status,
        }
    # return the captured result
    return result

@app.get('/expenses/user/{user_id}')
def list_user_expenses(user_id: int):
    with get_session() as s:
        expenses = s.exec(select(Expense).where(Expense.submitter_id == user_id)).all()
    return expenses

@app.get('/approvals/user/{user_id}/pending')
def pending_for_user(user_id: int):
    with get_session() as s:
        # find approval steps assigned to user and not completed where expense still pending
        rows = s.exec(select(ApprovalStep).where(ApprovalStep.approver_id == user_id).where(ApprovalStep.completed == False)).all()
        pending = []
        for r in rows:
            exp = s.get(Expense, r.expense_id)
            if exp and exp.status == 'pending':
                pending.append({"expense": exp, "step_id": r.id, "sequence": r.sequence})
    return pending

@app.post('/approvals/{expense_id}/decision')
def make_decision(expense_id: int, approver_id: int = Body(...), approved: bool = Body(...), comment: Optional[str] = Body(None), current=Depends(get_current_user)):
    with get_session() as s:
        expense = s.get(Expense, expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail='expense not found')
        # require that the caller is either the approver themselves or an admin
        if not current:
            raise HTTPException(status_code=401, detail='authentication required')
        if current.get('role') != 'admin' and current.get('user_id') != approver_id:
            raise HTTPException(status_code=403, detail='only the approver or admin can make decisions')

        # find current active step for this approver
        step = s.exec(select(ApprovalStep).where(ApprovalStep.expense_id == expense_id).where(ApprovalStep.approver_id == approver_id).where(ApprovalStep.completed == False)).first()
        if not step:
            raise HTTPException(status_code=400, detail='no pending approval step for this approver')
        # record decision
        dec = ApprovalDecision(expense_id=expense_id, approver_id=approver_id, approved=approved, comment=comment)
        s.add(dec)
        # mark step complete
        step.completed = True
        s.add(step)
        s.commit()
        # evaluate rules for company
        rule = s.exec(select(ApprovalRule).where(ApprovalRule.company_id == expense.company_id)).first()
        # gather decisions for expense
        decisions = s.exec(select(ApprovalDecision).where(ApprovalDecision.expense_id == expense_id)).all()
        # check special approver
        special_ok = False
        if rule and rule.special_approver_ids:
            ids = [int(x) for x in rule.special_approver_ids.split(',') if x.strip()]
            for d in decisions:
                if d.approved and d.approver_id in ids:
                    special_ok = True
        if special_ok:
            expense.status = 'approved'
            s.add(expense); s.commit()
            return {"status": "approved", "reason": "special approver approved"}
        # percentage rule
        if rule and rule.percentage_threshold:
            # count total approvers for this expense
            total = s.exec(select(ApprovalStep).where(ApprovalStep.expense_id == expense_id)).all()
            total_count = len(total)
            approve_count = len([d for d in decisions if d.approved])
            pct = (approve_count / total_count * 100) if total_count else 0
            if pct >= rule.percentage_threshold:
                expense.status = 'approved'
                s.add(expense); s.commit()
                return {"status": "approved", "reason": f"{pct}% approvals >= {rule.percentage_threshold}%"}
        # else, if any pending steps remain in sequence, move on; if none -> rejected
        pending_steps = s.exec(select(ApprovalStep).where(ApprovalStep.expense_id == expense_id).where(ApprovalStep.completed == False)).all()
        if not pending_steps:
            # if any decision was rejection, mark rejected, else approved
            if any(not d.approved for d in decisions):
                expense.status = 'rejected'
            else:
                expense.status = 'approved'
            s.add(expense); s.commit()
            return {"status": expense.status, "reason": "finalized"}
        else:
            # still pending
            s.commit()
            return {"status": "pending", "reason": "moved to next approver"}


@app.post('/ocr/receipt')
def ocr_receipt(file: UploadFile = File(...)):
    """
    OCR stub: accepts a receipt image and returns a mocked parsed expense.
    To enable real OCR, install Tesseract and pytesseract and replace the body with actual parsing.
    """
    # For prototype return a mocked parsed result
    return {
        "amount": 42.50,
        "currency": "USD",
        "date": date.today().isoformat(),
        "description": "Mocked OCR parsed receipt",
        "lines": [
            {"label": "Lunch", "amount": 42.50}
        ]
    }
