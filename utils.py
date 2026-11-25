import hashlib
from functools import wraps
from flask import session, redirect, url_for, request
from db import get_db


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


def verify_password(pwd: str, hashed: str) -> bool:
    return hash_password(pwd) == hashed


def current_user():
    return session.get("user")


def login_required(role=None):
    """
    role 可选值：
      - None       : 只要登录即可，未登录按路径跳对应端登录页
      - "admin"    : 必须是 admin 或 admin 兼容
      - "mobile"   : 必须是 mobile 或 admin 兼容
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            is_mobile_path = request.path.startswith("/m/")

            # 未登录
            if not user:
                if is_mobile_path:
                    return redirect(url_for("mobile.login"))
                return redirect(url_for("admin.login"))

            # 角色校验
            if role:
                user_role = user.get("role")
                # admin 通行所有；其他角色必须匹配
                if user_role != role and user_role != "admin":
                    if is_mobile_path:
                        return redirect(url_for("mobile.home"))
                    return redirect(url_for("admin.materials"))

            return fn(*args, **kwargs)
        return wrapper
    return deco


def log_action(action, target="", detail=""):
    user = session.get("user") or {}
    db = get_db()
    db.execute(
        "INSERT INTO operation_logs(user_name,action,target,detail,ip) VALUES(?,?,?,?,?)",
        (user.get("display_name") or user.get("username", "anonymous"),
         action, target, detail, request.remote_addr),
    )
    db.commit()


# ============================================================
# 权限系统
# ============================================================

# 模块定义：key -> 支持的动作
PERM_MODULES = {
    "materials": {"view", "edit"},
    "types":     {"view", "edit"},
    "users":     {"view", "edit"},
    "qrcodes":   {"view"},
    "records":   {"view"},
    "logs":      {"view"},
    "stats":     {"view"},
}

# 中文名（用于页面展示）
PERM_MODULE_NAMES = {
    "materials": "物料管理",
    "types":     "物料类别",
    "users":     "人员管理",
    "qrcodes":   "二维码打印",
    "records":   "出入库记录",
    "logs":      "操作日志",
    "stats":     "数据统计",
}

def is_super_admin():
    user = session.get("user") or {}
    return user.get("username") == "admin"

def is_admin_user():
    """当前登录用户是不是超级 admin 账号"""
    user = session.get("user") or {}
    return user.get("username") == "admin"


def has_perm(module: str, action: str = "view") -> bool:
    """
    判断当前登录用户是否有权限
    - admin 账号永远 True
    - 其他用户查 permissions 表
    - action='edit' 时要求 can_edit=1
    - action='view' 时要求 can_view=1 或 can_edit=1
    """
    user = session.get("user")
    if not user:
        return False

    # admin 超级账号
    if user.get("username") == "admin":
        return True

    db = get_db()
    row = db.execute(
        "SELECT can_view, can_edit FROM permissions WHERE user_id=? AND module=?",
        (user["id"], module),
    ).fetchone()

    if not row:
        return False

    if action == "edit":
        return bool(row["can_edit"])
    # view：can_view 或 can_edit 任一为真都算
    return bool(row["can_view"]) or bool(row["can_edit"])


def get_user_perms(user_id: int) -> dict:
    """读取某用户的全部权限，返回 {module: {'view':bool, 'edit':bool}}"""
    db = get_db()
    rows = db.execute(
        "SELECT module, can_view, can_edit FROM permissions WHERE user_id=?",
        (user_id,),
    ).fetchall()
    result = {m: {"view": False, "edit": False} for m in PERM_MODULES}
    for r in rows:
        result[r["module"]] = {
            "view": bool(r["can_view"]),
            "edit": bool(r["can_edit"]),
        }
    return result


def save_user_perms(user_id: int, perms: dict):
    """
    写入某用户的权限
    perms 结构：{module: {'view':bool, 'edit':bool}}
    只处理 PERM_MODULES 中定义的模块
    """
    db = get_db()
    for module in PERM_MODULES:
        p = perms.get(module, {})
        view = 1 if p.get("view") or p.get("edit") else 0
        edit = 1 if p.get("edit") else 0
        db.execute(
            """INSERT INTO permissions(user_id, module, can_view, can_edit)
               VALUES(?,?,?,?)
               ON CONFLICT(user_id, module)
               DO UPDATE SET can_view=excluded.can_view, can_edit=excluded.can_edit""",
            (user_id, module, view, edit),
        )
    db.commit()


def require_perm(module: str, action: str = "view"):
    """
    装饰器：要求当前用户有该权限，否则 403
    用法：@require_perm("materials", "edit")
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_perm(module, action):
                # AJAX 请求 → JSON
                if request.path.startswith("/api/") or \
                   request.headers.get("X-Requested-With") == "XMLHttpRequest" or \
                   request.is_json:
                    return jsonify(ok=False, msg="无权限"), 403
                # 页面请求 → 提示页
                return render_template("admin/403.html"), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco