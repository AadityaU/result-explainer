-- Data model for a fictional online store, calendar year 2025.
-- All data is synthetic (see src/result_explainer/generate.py).
-- Money is stored as integer cents; queries convert to dollars.
-- Dates are ISO-8601 text (YYYY-MM-DD).

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    region       TEXT    NOT NULL CHECK (region IN ('North', 'South', 'East', 'West', 'Central')),
    segment      TEXT    NOT NULL CHECK (segment IN ('consumer', 'business')),
    signup_date  TEXT    NOT NULL
);

CREATE TABLE products (
    product_id        INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL UNIQUE,
    category          TEXT    NOT NULL,
    unit_price_cents  INTEGER NOT NULL CHECK (unit_price_cents > 0)
);
