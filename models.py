from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import date as dt_date
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import Date

class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    country: str
    currency: str

    users: List["User"] = Relationship(back_populates="company")
    expenses: List["Expense"] = Relationship(back_populates="company")

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    role: str = "employee"  # admin, manager, employee
    password_hash: Optional[str] = None
    manager_id: Optional[int] = Field(default=None, foreign_key="user.id")
    company_id: Optional[int] = Field(default=None, foreign_key="company.id")

    company: Optional[Company] = Relationship(back_populates="users")

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    submitter_id: int = Field(foreign_key="user.id")
    company_id: int = Field(foreign_key="company.id")
    amount: float
    currency: str
    amount_company_currency: float
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[dt_date] = Field(default=None, sa_column=Column(Date))
    status: str = Field(default="pending")  # pending, approved, rejected

    approvals: List["ApprovalStep"] = Relationship(back_populates="expense")
    decisions: List["ApprovalDecision"] = Relationship(back_populates="expense")
    company: Optional[Company] = Relationship(back_populates="expenses")

class ApprovalStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id")
    approver_id: int = Field(foreign_key="user.id")
    sequence: int = 0
    completed: bool = False

    expense: Optional[Expense] = Relationship(back_populates="approvals")

class ApprovalDecision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expense.id")
    approver_id: int = Field(foreign_key="user.id")
    approved: bool
    comment: Optional[str] = None

    expense: Optional[Expense] = Relationship(back_populates="decisions")

class ApprovalRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    # percentage threshold as integer 0-100, nullable
    percentage_threshold: Optional[int] = None
    # list of special approver user ids serialized as CSV for simplicity
    special_approver_ids: Optional[str] = None
    # behavior: 'and' or 'or' between rules (not fully fleshed out in prototype)
    mode: Optional[str] = 'or'
