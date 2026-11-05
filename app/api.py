import calendar
import csv
import io
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from . import ai
from .auth import valid_password
from .models import CATEGORIES, Expense, MonthlyPlan, db

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.before_request
@login_required
def _require_login():
    return None


@bp.errorhandler(ValueError)
def _bad_value(e):
    return jsonify(error=str(e)), 400


def err(msg, code=400):
    return jsonify(error=msg), code


# ---------- helpers ----------
def month_arg():
    m = request.args.get("month") or date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", m):
        raise ValueError("Invalid month. Use YYYY-MM.")
    return m


def bounds(m):
    y, mo = map(int, m.split("-"))
    return date(y, mo, 1), date(y + (mo == 12), mo % 12 + 1, 1)


def shift(m, n):
    y, mo = map(int, m.split("-"))
    t = y * 12 + mo - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def label(m):
    y, mo = map(int, m.split("-"))
    return f"{calendar.month_abbr[mo]} {y % 100:02d}"


def money(v, field, allow_zero=False):
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} must be a number.")
    if d < 0 or (d == 0 and not allow_zero) or d > Decimal("10000000"):
        raise ValueError(f"{field} is out of the allowed range.")
    return d


def parse_expense(d):
    if not isinstance(d, dict):
        raise ValueError("Invalid data.")
    amount = money(d.get("amount"), "Amount")
    category = d.get("category")
    if category not in CATEGORIES:
        raise ValueError("Please choose a valid category.")
    try:
        when = date.fromisoformat(str(d.get("date")))
    except ValueError:
        raise ValueError("Please enter a valid date.")
    if when > date.today() + timedelta(days=366) or when.year < 2000:
        raise ValueError("Date is out of range.")
    desc = str(d.get("description") or "").strip()
    if len(desc) > 200:
        raise ValueError("Description is too long (max 200 characters).")
    return amount, category, when, desc


def cat_totals(uid, m):
    s, e = bounds(m)
    rows = (db.session.query(Expense.category, func.sum(Expense.amount))
            .filter(Expense.user_id == uid, Expense.expense_date >= s, Expense.expense_date < e)
            .group_by(Expense.category).all())
    return {c: float(t) for c, t in rows}


def month_total(uid, m):
    return round(sum(cat_totals(uid, m).values()), 2)


def get_plan(uid, m):
    """Exact plan for the month, else the most recent earlier plan (pocket money usually repeats)."""
    p = MonthlyPlan.query.filter_by(user_id=uid, month=m).first()
    if p:
        return float(p.income), float(p.budget), False
    p = (MonthlyPlan.query.filter(MonthlyPlan.user_id == uid, MonthlyPlan.month < m)
         .order_by(MonthlyPlan.month.desc()).first())
    if p:
        return float(p.income), float(p.budget), True
    return 0.0, 0.0, False


def summary(uid, m):
    s, e = bounds(m)
    income, budget, inherited = get_plan(uid, m)
    cats = cat_totals(uid, m)
    spent = round(sum(cats.values()), 2)
    today, dim = date.today(), (e - s).days
    is_current = s <= today < e
    day = today.day if is_current else (dim if e <= today else 1)
    categories = [{"category": c, "total": t, "pct": round(t / spent * 100, 1) if spent else 0}
                  for c, t in sorted(cats.items(), key=lambda x: -x[1])]
    return {"month": m, "income": income, "budget": budget, "spent": spent,
            "balance": round(income - spent, 2), "budget_left": round(budget - spent, 2),
            "budget_used_pct": round(spent / budget * 100, 1) if budget else 0,
            "categories": categories, "days_in_month": dim, "day_of_month": day,
            "is_current": is_current, "plan_inherited": inherited}


def build_prediction(uid):
    cur = date.today().strftime("%Y-%m")
    months = [shift(cur, -i) for i in range(6, 0, -1)]
    per_month = [cat_totals(uid, m) for m in months]
    totals = [round(sum(c.values()), 2) for c in per_month]
    while totals and totals[0] == 0:
        months.pop(0); totals.pop(0); per_month.pop(0)
    basis = "Based on your past monthly spending (trend + recent-weighted average)."
    if not totals:
        s = summary(uid, cur)
        if s["spent"] <= 0:
            return {"next_month": shift(cur, 1), "next_label": label(shift(cur, 1)), "predicted_total": 0,
                    "confidence": "none", "months_used": 0, "basis": "Add some expenses to unlock predictions.",
                    "by_category": [], "history": []}
        f = s["days_in_month"] / max(s["day_of_month"], 1)
        months, totals = [cur], [round(s["spent"] * f, 2)]
        per_month = [{c["category"]: c["total"] * f for c in s["categories"]}]
        basis = "Based on this month's spending so far, projected to month-end."
    predicted = ai.forecast(totals)
    raw = {c: ai.forecast([pm.get(c, 0) for pm in per_month]) for c in CATEGORIES}
    raw_sum = sum(raw.values())
    scale = predicted / raw_sum if raw_sum else 0
    by_cat = sorted(({"category": c, "predicted": round(v * scale, 2)} for c, v in raw.items() if v * scale >= 1),
                    key=lambda x: -x["predicted"])
    nxt = shift(cur, 1)
    return {"next_month": nxt, "next_label": label(nxt), "predicted_total": round(predicted, 2),
            "confidence": ai.confidence_for(len(totals)), "months_used": len(totals), "basis": basis,
            "by_category": by_cat,
            "history": [{"month": m, "label": label(m), "total": t} for m, t in zip(months, totals)]}


# ---------- routes ----------
@bp.get("/summary")
def summary_route():
    return jsonify(summary(current_user.id, month_arg()))


@bp.get("/expenses")
def list_expenses():
    q = Expense.query.filter_by(user_id=current_user.id)
    if request.args.get("month") != "all":
        s, e = bounds(month_arg())
        q = q.filter(Expense.expense_date >= s, Expense.expense_date < e)
    cat = request.args.get("category")
    if cat:
        q = q.filter(Expense.category == cat)
    term = request.args.get("q", "").strip()[:50]
    if term:
        q = q.filter(Expense.description.ilike(f"%{term}%"))
    try:
        limit = min(max(int(request.args.get("limit", 500)), 1), 1000)
    except ValueError:
        limit = 500
    rows = q.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])


@bp.post("/expenses")
def add_expense():
    amount, category, when, desc = parse_expense(request.get_json(silent=True))
    x = Expense(user_id=current_user.id, amount=amount, category=category, expense_date=when, description=desc)
    db.session.add(x)
    db.session.commit()
    return jsonify(x.to_dict()), 201


def _own(expense_id):
    return Expense.query.filter_by(id=expense_id, user_id=current_user.id).first()


@bp.put("/expenses/<int:expense_id>")
def edit_expense(expense_id):
    x = _own(expense_id)
    if not x:
        return err("Expense not found.", 404)
    x.amount, x.category, x.expense_date, x.description = parse_expense(request.get_json(silent=True))
    db.session.commit()
    return jsonify(x.to_dict())


@bp.delete("/expenses/<int:expense_id>")
def delete_expense(expense_id):
    x = _own(expense_id)
    if not x:
        return err("Expense not found.", 404)
    db.session.delete(x)
    db.session.commit()
    return jsonify(ok=True)


@bp.get("/plan")
def get_plan_route():
    m = month_arg()
    income, budget, inherited = get_plan(current_user.id, m)
    return jsonify(month=m, income=income, budget=budget, inherited=inherited)


@bp.put("/plan")
def put_plan():
    m = month_arg()
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("Invalid data.")
    income, budget = money(d.get("income"), "Income", True), money(d.get("budget"), "Budget", True)
    p = MonthlyPlan.query.filter_by(user_id=current_user.id, month=m).first()
    if not p:
        p = MonthlyPlan(user_id=current_user.id, month=m)
        db.session.add(p)
    p.income, p.budget = income, budget
    db.session.commit()
    return jsonify(month=m, income=float(income), budget=float(budget), inherited=False)


@bp.get("/charts/monthly")
def chart_monthly():
    end = month_arg()
    months = [shift(end, -i) for i in range(5, -1, -1)]
    plans = {p.month: float(p.budget) for p in MonthlyPlan.query.filter(
        MonthlyPlan.user_id == current_user.id, MonthlyPlan.month.in_(months))}
    return jsonify(labels=[label(m) for m in months],
                   totals=[month_total(current_user.id, m) for m in months],
                   budgets=[plans.get(m, 0) for m in months])


@bp.get("/predict")
def predict_route():
    return jsonify(build_prediction(current_user.id))


@bp.get("/suggestions")
def suggestions_route():
    s = summary(current_user.id, month_arg())
    return jsonify(suggestions=ai.build_suggestions(s, build_prediction(current_user.id)))


@bp.get("/report")
def report_route():
    m = month_arg()
    s = summary(current_user.id, m)
    start, end = bounds(m)
    rows = (Expense.query.filter(Expense.user_id == current_user.id, Expense.expense_date >= start,
                                 Expense.expense_date < end).order_by(Expense.amount.desc()).all())
    per_day = {}
    for r in rows:
        per_day[r.expense_date.day] = per_day.get(r.expense_date.day, 0) + float(r.amount)
    daily = [{"date": date(start.year, start.month, d).isoformat(), "total": round(per_day.get(d, 0), 2)}
             for d in range(1, s["day_of_month"] + 1)]
    busiest = max(per_day.items(), key=lambda kv: kv[1]) if per_day else None
    return jsonify(summary=s, daily=daily, count=len(rows),
                   avg_per_day=round(s["spent"] / max(s["day_of_month"], 1), 2),
                   busiest_day=({"date": date(start.year, start.month, busiest[0]).isoformat(),
                                 "total": round(busiest[1], 2)} if busiest else None),
                   top_expenses=[r.to_dict() for r in rows[:5]])


def _safe(v):
    v = str(v or "")
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v  # stops CSV/Excel formula injection


@bp.get("/export.csv")
def export_csv():
    q = Expense.query.filter_by(user_id=current_user.id)
    name = "all"
    if request.args.get("month") != "all":
        name = month_arg()
        s, e = bounds(name)
        q = q.filter(Expense.expense_date >= s, Expense.expense_date < e)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Category", "Description", "Amount (INR)"])
    for x in q.order_by(Expense.expense_date, Expense.id):
        w.writerow([x.expense_date.isoformat(), x.category, _safe(x.description), f"{x.amount:.2f}"])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=expenses_{name}.csv"})


@bp.get("/profile")
def get_profile():
    u = current_user
    return jsonify(name=u.name, email=u.email, course=u.course or "", college=u.college or "",
                   joined=u.created_at.date().isoformat() if u.created_at else "")


@bp.put("/profile")
def put_profile():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("Invalid data.")
    name = str(d.get("name", "")).strip()
    if not 2 <= len(name) <= 80:
        raise ValueError("Name must be 2 to 80 characters.")
    course, college = str(d.get("course", "")).strip(), str(d.get("college", "")).strip()
    if len(course) > 80 or len(college) > 120:
        raise ValueError("Course or college name is too long.")
    current_user.name, current_user.course, current_user.college = name, course, college
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/profile/password")
def change_password():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("Invalid data.")
    if not current_user.check_password(str(d.get("current_password", ""))):
        return err("Current password is incorrect.", 400)
    new = str(d.get("new_password", ""))
    if not valid_password(new):
        raise ValueError("New password must be 8+ characters with a letter and a number.")
    current_user.set_password(new)
    db.session.commit()
    return jsonify(ok=True)
