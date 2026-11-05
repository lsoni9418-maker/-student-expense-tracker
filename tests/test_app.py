import pytest
from app import create_app
from app.ai import build_suggestions, confidence_for, forecast


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://",
                       "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test-secret"})


def register(c, email="asha@example.com", name="Asha", pw="Passw0rd1"):
    return c.post("/register", data={"name": name, "email": email, "password": pw, "confirm": pw})


EXP = {"amount": "250.50", "category": "Food & Snacks", "date": "2026-11-02", "description": "Lunch"}


def test_register_login_logout(app):
    c = app.test_client()
    assert register(c).status_code == 302
    assert c.get("/app").status_code == 200
    c.post("/logout")
    assert c.get("/app").status_code == 302
    r = c.post("/login", data={"email": "asha@example.com", "password": "Passw0rd1"})
    assert r.status_code == 302


def test_bad_login_and_weak_password(app):
    c = app.test_client()
    assert register(c, pw="short").status_code == 400
    register(c)
    c2 = app.test_client()
    assert c2.post("/login", data={"email": "asha@example.com", "password": "wrong"}).status_code == 401


def test_api_requires_login(app):
    assert app.test_client().get("/api/expenses").status_code == 401


def test_expense_crud_and_validation(app):
    c = app.test_client()
    register(c)
    r = c.post("/api/expenses", json=EXP)
    assert r.status_code == 201
    eid = r.get_json()["id"]
    assert c.post("/api/expenses", json={**EXP, "amount": "-5"}).status_code == 400
    assert c.post("/api/expenses", json={**EXP, "category": "Hacking"}).status_code == 400
    assert c.post("/api/expenses", json={**EXP, "date": "nope"}).status_code == 400
    assert c.put(f"/api/expenses/{eid}", json={**EXP, "amount": "300"}).get_json()["amount"] == 300
    assert c.delete(f"/api/expenses/{eid}").status_code == 200
    assert c.get("/api/expenses?month=all").get_json() == []


def test_users_cannot_see_each_others_data(app):
    a, b = app.test_client(), app.test_client()
    register(a, "a@example.com")
    register(b, "b@example.com", "Bala")
    eid = a.post("/api/expenses", json=EXP).get_json()["id"]
    assert b.get("/api/expenses?month=all").get_json() == []
    assert b.put(f"/api/expenses/{eid}", json=EXP).status_code == 404
    assert b.delete(f"/api/expenses/{eid}").status_code == 404
    assert len(a.get("/api/expenses?month=all").get_json()) == 1


def test_plan_summary_and_csv(app):
    c = app.test_client()
    register(c)
    c.put("/api/plan?month=2026-11", json={"income": "5000", "budget": "4000"})
    c.post("/api/expenses", json=EXP)
    s = c.get("/api/summary?month=2026-11").get_json()
    assert s["income"] == 5000 and s["spent"] == 250.5 and s["balance"] == 4749.5
    c.post("/api/expenses", json={**EXP, "description": "=cmd()"})
    csv_text = c.get("/api/export.csv?month=2026-11").get_data(as_text=True)
    assert "Lunch" in csv_text and "'=cmd()" in csv_text
    assert c.get("/api/predict").status_code == 200
    assert c.get("/api/suggestions?month=2026-11").status_code == 200
    assert c.get("/api/summary?month=bad").status_code == 400


def test_forecast_logic():
    assert forecast([]) == 0
    assert forecast([1000]) == 1000
    assert forecast([1000, 1000, 1000]) == pytest.approx(1000)
    assert forecast([1000, 1200, 1400, 1600]) > 1400
    assert forecast([500, 100]) >= 0
    assert confidence_for(1) == "low" and confidence_for(3) == "medium" and confidence_for(5) == "high"


def test_suggestions():
    base = {"spent": 5000, "income": 4000, "budget": 3000, "days_in_month": 30, "day_of_month": 15,
            "is_current": True, "categories": [{"category": "Food & Snacks", "total": 3000, "pct": 60}]}
    types = [t["type"] for t in build_suggestions(base, None)]
    assert "danger" in types
    assert build_suggestions({**base, "spent": 0}, None)[0]["type"] == "info"
