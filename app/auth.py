import re
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import CATEGORIES, User, db

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def valid_password(p):
    return 8 <= len(p) <= 128 and re.search(r"[A-Za-z]", p) and re.search(r"\d", p)


@bp.route("/")
def index():
    return redirect(url_for("auth.dashboard" if current_user.is_authenticated else "auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        course = request.form.get("course", "").strip()[:80]
        pw, confirm = request.form.get("password", ""), request.form.get("confirm", "")
        error = None
        if not 2 <= len(name) <= 80:
            error = "Please enter your name (2 to 80 characters)."
        elif len(email) > 120 or not EMAIL_RE.match(email):
            error = "Please enter a valid email address."
        elif not valid_password(pw):
            error = "Password must be 8+ characters and include a letter and a number."
        elif pw != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(email=email).first():
            error = "An account with this email already exists."
        if error:
            flash(error, "error")
            return render_template("auth.html", mode="register", form=request.form), 400
        user = User(name=name, email=email, course=course)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        session.clear()
        login_user(user)
        session.permanent = True
        return redirect(url_for("auth.dashboard"))
    return render_template("auth.html", mode="register", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            session.clear()
            login_user(user)
            session.permanent = True
            return redirect(url_for("auth.dashboard"))
        flash("Invalid email or password.", "error")
        return render_template("auth.html", mode="login", form=request.form), 401
    return render_template("auth.html", mode="login", form={})


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/app")
@login_required
def dashboard():
    return render_template("app.html", categories=CATEGORIES)
