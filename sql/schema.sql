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

-- Cancelled orders never ship, so they have no ship or delivery date.
CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers (customer_id),
    order_date     TEXT    NOT NULL,
    channel        TEXT    NOT NULL CHECK (channel IN ('web', 'mobile', 'marketplace')),
    status         TEXT    NOT NULL CHECK (status IN ('delivered', 'cancelled')),
    ship_date      TEXT,
    delivery_date  TEXT,
    CHECK ((status = 'delivered') = (delivery_date IS NOT NULL))
);

-- unit_price_cents is the price at the time of the order.
CREATE TABLE order_items (
    order_id          INTEGER NOT NULL REFERENCES orders (order_id),
    product_id        INTEGER NOT NULL REFERENCES products (product_id),
    quantity          INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents  INTEGER NOT NULL CHECK (unit_price_cents > 0),
    discount_pct      INTEGER NOT NULL DEFAULT 0 CHECK (discount_pct IN (0, 10, 20)),
    PRIMARY KEY (order_id, product_id)
);
