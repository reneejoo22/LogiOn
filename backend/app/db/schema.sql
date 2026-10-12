-- 테이블 설명은 backend/DB_DESIGN.md 참고

CREATE TABLE IF NOT EXISTS drivers (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    area           TEXT NOT NULL,
    vehicle_number TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    short_name TEXT NOT NULL UNIQUE,
    address    TEXT NOT NULL,
    phone      TEXT,
    lat        REAL,
    lng        REAL
);

CREATE TABLE IF NOT EXISTS products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
             CHECK (category IN ('tobacco', 'ambient_drink', 'chilled', 'ready_meal')),
    barcode  TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS product_aliases (
    product_id INTEGER NOT NULL REFERENCES products(id),
    alias      TEXT NOT NULL,
    PRIMARY KEY (product_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_alias ON product_aliases(alias);

CREATE TABLE IF NOT EXISTS routes (
    id           INTEGER PRIMARY KEY,
    driver_id    INTEGER NOT NULL REFERENCES drivers(id),
    service_date TEXT NOT NULL,
    depart_at    TEXT,
    est_end_at   TEXT,
    synced_at    TEXT,
    UNIQUE (driver_id, service_date)
);

CREATE TABLE IF NOT EXISTS stops (
    id           INTEGER PRIMARY KEY,
    route_id     INTEGER NOT NULL REFERENCES routes(id),
    store_id     INTEGER NOT NULL REFERENCES stores(id),
    seq          INTEGER NOT NULL,
    eta          TEXT NOT NULL,
    distance_km  REAL,
    notice       TEXT,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'done')),
    completed_at TEXT,
    receiver     TEXT,
    updated_at   TEXT NOT NULL,
    UNIQUE (route_id, seq),
    UNIQUE (route_id, store_id)
);

CREATE TABLE IF NOT EXISTS stop_zones (
    stop_id    INTEGER NOT NULL REFERENCES stops(id),
    category   TEXT NOT NULL
               CHECK (category IN ('tobacco', 'ambient_drink', 'chilled', 'ready_meal')),
    boxes      INTEGER NOT NULL DEFAULT 0,
    checked    INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (stop_id, category)
);

CREATE TABLE IF NOT EXISTS stop_items (
    id         INTEGER PRIMARY KEY,
    stop_id    INTEGER NOT NULL REFERENCES stops(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    unit       TEXT NOT NULL CHECK (unit IN ('개', '박스', '판', '봉지')),
    UNIQUE (stop_id, product_id)
);

CREATE TABLE IF NOT EXISTS issues (
    id         INTEGER PRIMARY KEY,
    stop_id    INTEGER NOT NULL REFERENCES stops(id),
    product_id INTEGER REFERENCES products(id),
    type       TEXT NOT NULL
               CHECK (type IN ('파손', '수량부족', '오배송', '온도이상')),
    qty        INTEGER,
    unit       TEXT CHECK (unit IN ('개', '박스', '판', '봉지')),
    source     TEXT NOT NULL CHECK (source IN ('voice', 'touch')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS utterance_logs (
    id          INTEGER PRIMARY KEY,
    stop_id     INTEGER REFERENCES stops(id),
    text        TEXT NOT NULL,
    intent      TEXT,
    intent_conf REAL,
    llm_raw     TEXT,
    resolved    TEXT,
    reply       TEXT,
    latency_ms  INTEGER,
    created_at  TEXT NOT NULL
);
