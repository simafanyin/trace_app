import sqlite3
from flask import g
from config import Config

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'mobile',
    display_name TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS materials_type (
    type_id TEXT PRIMARY KEY,
    type_no TEXT UNIQUE,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materials (
    material_no TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    spec TEXT,
    category_0 TEXT,       -- P：产品， T：工具
    category TEXT,         -- 子项分类
    unit TEXT,
    remark TEXT,
    sku TEXT,    
    quantity INTEGER DEFAULT 0,
    image TEXT,            -- 原图相对路径
    image_thumb TEXT,      -- 缩略图相对路径
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    warn_qty INTEGER       -- 警戒值
);

CREATE TABLE IF NOT EXISTS in_out_bound_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_no TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    in_or_out TEXT NOT NULL,
    operator TEXT,
    belong TEXT,
    remark TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS stocktake_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_no TEXT NOT NULL,
    before_qty INTEGER,
    after_qty INTEGER,
    operator TEXT,
    remark TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT,
    action TEXT,
    target TEXT,
    detail TEXT,
    ip TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    module TEXT NOT NULL,
    can_view INTEGER DEFAULT 0,
    can_edit INTEGER DEFAULT 0,
    UNIQUE(user_id, module),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(Config.DB_PATH, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
        g.db.execute("PRAGMA foreign_keys=ON;")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """建表 + 默认账号 + 默认分类"""
    import os
    from utils import hash_password

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.UPLOAD_ORIGINAL, exist_ok=True)
    os.makedirs(Config.UPLOAD_THUMB, exist_ok=True)

    conn = sqlite3.connect(Config.DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users(user_name,password_hash,role,display_name) VALUES(?,?,?,?)",
            ("admin", hash_password("admin123"), "admin", "系统管理员"),
        )

    conn.commit()
    conn.close()

    app.teardown_appcontext(close_db)