# ============================================================
# 对现有数据库里的非 admin 用户，可能需要手动补一份权限，一次性脚本
# ============================================================
import sqlite3
from config import Config

conn = sqlite3.connect(Config.DB_PATH)
conn.row_factory = sqlite3.Row

MODULES = ["materials","types","users","qrcodes","records","logs","stats"]

users = conn.execute("SELECT id, user_name FROM users").fetchall()
for u in users:
    if u["user_name"] == "admin":
        continue
    for m in MODULES:
        conn.execute(
            """INSERT OR IGNORE INTO permissions(user_id, module, can_view, can_edit)
               VALUES(?,?,?,?)""",
            (u["id"], m, 1, 0),
        )

conn.commit()
conn.close()
print("默认权限已补齐")