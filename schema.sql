DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS user_activity;
DROP TABLE IF EXISTS ml_predictions;
DROP TABLE IF EXISTS users;

CREATE TABLE bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    date TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payment_status TEXT DEFAULT 'pending',
    payment_id TEXT,
    amount REAL DEFAULT 50.0,
    players INTEGER DEFAULT 10
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    payment_id TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'usd',
    status TEXT NOT NULL,
    payment_method TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings (id)
);

CREATE TABLE user_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    ip_address TEXT,
    action TEXT NOT NULL,
    page TEXT,
    timestamp TEXT NOT NULL,
    user_agent TEXT,
    referrer TEXT
);

CREATE TABLE ml_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_type TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login TEXT,
    is_admin INTEGER DEFAULT 0
);
