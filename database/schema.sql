-- Student Expense Tracker - PostgreSQL / Supabase schema
-- The Flask app creates these tables automatically on first run (db.create_all()).
-- Running this file manually in the Supabase SQL Editor is optional.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(80)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    course        VARCHAR(80)  DEFAULT '',
    college       VARCHAR(120) DEFAULT '',
    created_at    TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS expenses (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount       NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    category     VARCHAR(40)  NOT NULL,
    description  VARCHAR(200) DEFAULT '',
    expense_date DATE NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_expenses_user_date ON expenses (user_id, expense_date);

CREATE TABLE IF NOT EXISTS monthly_plans (
    id      SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month   VARCHAR(7) NOT NULL,            -- 'YYYY-MM'
    income  NUMERIC(12,2) NOT NULL DEFAULT 0,
    budget  NUMERIC(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT uq_user_month UNIQUE (user_id, month)
);

-- Supabase exposes tables through a public API. Turning on Row Level Security with no
-- policies blocks that public API. Flask connects as the "postgres" owner, so it is unaffected.
ALTER TABLE users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_plans ENABLE ROW LEVEL SECURITY;
