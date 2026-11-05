# Student Expense Tracker
**Smart Money Management for Students** — a full-stack web app where every student has a private account to track expenses in ₹, set pocket money and budgets, see charts, and get AI-based predictions and saving tips.

## Tech stack
Frontend: HTML, CSS, JavaScript, Chart.js · Backend: Python Flask, REST APIs, SQLAlchemy · Database: PostgreSQL (Supabase)

## Features
Registration and login · personal dashboard · add/edit/delete expenses · 9 categories · monthly income and budget · remaining balance · expense history with filters · monthly and category charts · AI next-month prediction · AI saving suggestions · printable monthly report · CSV export · profile and password settings

## Security
Password hashing (scrypt via Werkzeug) · Flask-Login sessions (HttpOnly, SameSite, 8-hour expiry) · CSRF protection on every form and API call · every query is filtered by the logged-in user's id · SQLAlchemy parameterised queries (SQL injection protection) · server-side input validation · secrets in environment variables · CSV formula-injection protection · security headers (CSP, X-Frame-Options, HSTS in production)

## Project structure
```
app/            Flask application (config, models, auth, api, ai, templates, static)
database/       schema.sql (PostgreSQL / Supabase)
tests/          pytest tests
wsgi.py         entry point
requirements.txt, .env.example, Procfile, render.yaml, .gitignore
```

## Quick start (local)
```
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env   then edit .env
python wsgi.py                 # open http://127.0.0.1:5000
```
With no `DATABASE_URL` set, the app uses a local SQLite file so you can try it immediately. Set `DATABASE_URL` to your Supabase connection string to use PostgreSQL.

## Run tests
```
pytest -q
```

## AI prediction
Next month's spending = 50% linear-regression trend + 50% recent-weighted average of up to 6 past months, calculated overall and per category. Suggestions are rule-based (budget use, spending pace, category share, savings rate, forecast vs. income).

## Deploy
`render.yaml` and `Procfile` are included. Set `SECRET_KEY`, `DATABASE_URL` and `FLASK_ENV=production` as environment variables on your host.
