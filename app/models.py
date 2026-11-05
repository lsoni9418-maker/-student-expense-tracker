from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

CATEGORIES = [
    "Food & Snacks", "Transport", "Education", "Rent & Hostel", "Entertainment",
    "Shopping", "Health", "Recharge & Bills", "Other",
]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    course = db.Column(db.String(80), default="")
    college = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=_now)
    expenses = db.relationship("Expense", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    plans = db.relationship("MonthlyPlan", backref="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(200), default="")
    expense_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    __table_args__ = (db.Index("ix_expenses_user_date", "user_id", "expense_date"),)

    def to_dict(self):
        return {"id": self.id, "amount": float(self.amount), "category": self.category,
                "description": self.description or "", "date": self.expense_date.isoformat()}


class MonthlyPlan(db.Model):
    __tablename__ = "monthly_plans"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    income = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    budget = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint("user_id", "month", name="uq_user_month"),)
