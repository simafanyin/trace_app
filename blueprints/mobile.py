from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from db import get_db
from utils import verify_password, login_required, log_action

mobile_bp = Blueprint("mobile", __name__, template_folder="../templates/mobile")

BELONG_OPTIONS = ["方一", "方二", "方三", "方向盘", "踏板", "基座", "支架", "其他"]


# ============================================================
# 登录 / 登出
# ============================================================
@mobile_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next") or request.form.get("next") or ""
    if request.method == "POST":
        u = request.form.get("user_name", "").strip()
        p = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE user_name=?", (u,)).fetchone()
        if row and verify_password(p, row["password_hash"]):
            session["user"] = {
                "id": row["id"],
                "username": row["user_name"],
                "role": row["role"],
                "display_name": row["display_name"],
            }
            log_action("登录", u)
            return redirect(next_url or url_for("mobile.home"))
        flash("账号或密码错误")
    return render_template("mobile/login.html", next_url=next_url)


@mobile_bp.route("/logout")
def logout():
    log_action("登出")
    session.pop("user", None)
    return redirect(url_for("mobile.login"))


# ============================================================
# 首页
# ============================================================
@mobile_bp.route("/home")
@login_required("mobile")
def home():
    db = get_db()
    rows = db.execute(
        "SELECT material_no, name, image_thumb, image FROM materials ORDER BY material_no ASC"
    ).fetchall()
    materials = [dict(r) for r in rows]
    return render_template("mobile/home.html", materials=materials)


# ============================================================
# 来料入库
# ============================================================
@mobile_bp.route("/inbound", methods=["GET", "POST"])
@login_required("mobile")
def inbound():
    db = get_db()

    if request.method == "POST":
        f = request.form
        no = f["material_no"].strip()
        qty = int(f.get("quantity") or 0)
        if qty <= 0:
            return jsonify(ok=False, msg="数量必须大于 0")

        exist = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
        if exist:
            db.execute(
                """UPDATE materials SET name=?,spec=?,category=?,unit=?,remark=?,
                   quantity=quantity+?, updated_at=datetime('now','localtime')
                   WHERE material_no=?""",
                (
                    f.get("name", exist["name"]),
                    f.get("spec", exist["spec"]),
                    f.get("category", exist["category"]),
                    f.get("unit", exist["unit"]),
                    f.get("remark", exist["remark"]),
                    qty,
                    no,
                ),
            )
        else:
            db.execute(
                """INSERT INTO materials(material_no,name,spec,category,unit,remark,quantity)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    no,
                    f.get("name", ""),
                    f.get("spec", ""),
                    f.get("category", ""),
                    f.get("unit", ""),
                    f.get("remark", ""),
                    qty,
                ),
            )

        user = session["user"]
        db.execute(
            """INSERT INTO in_out_bound_records(material_no,quantity,in_or_out,operator,remark)
               VALUES(?,?,?,?,?)""",
            (no, qty, "in", user["display_name"] or user["username"], f.get("remark", "")),
        )
        db.commit()
        log_action("来料入库", no, f"+{qty}")
        return jsonify(ok=True, redirect=url_for("mobile.done", msg="入库成功"))

    # 分类下拉需要
    types_rows = db.execute("SELECT * FROM materials_type ORDER BY type_no").fetchall()
    types = [dict(t) for t in types_rows]
    return render_template("mobile/inbound.html", types=types)


# ============================================================
# 扫码
# ============================================================
@mobile_bp.route("/scan")
@login_required("mobile")
def scan():
    no = request.args.get("materialNo", "").strip()
    if not no:
        return render_template("mobile/scan.html")

    db = get_db()
    material = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not material:
        return render_template("mobile/done.html", msg=f"未找到物料 {no}"), 404

    return render_template("mobile/scan.html", material=dict(material))


# ============================================================
# 领用出库
# ============================================================
@mobile_bp.route("/outbound", methods=["GET", "POST"])
@login_required("mobile")
def outbound():
    db = get_db()

    if request.method == "POST":
        f = request.form
        no  = f["material_no"].strip()
        qty = int(f.get("quantity") or 0)
        belong = f.get("belong", "").strip()

        # ✅ 归属必填校验
        if not belong:
            return jsonify(ok=False, msg="请选择归属")
        if belong not in BELONG_OPTIONS:
            return jsonify(ok=False, msg="归属不合法")

        row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
        if not row:
            return jsonify(ok=False, msg="物料不存在")
        if qty <= 0 or qty > row["quantity"]:
            return jsonify(ok=False, msg="数量不合法或库存不足")

        db.execute(
            "UPDATE materials SET quantity=quantity-?, updated_at=datetime('now','localtime') WHERE material_no=?",
            (qty, no),
        )
        user = session["user"]
        db.execute(
            """INSERT INTO in_out_bound_records(material_no,quantity,in_or_out,operator,belong,remark)
            VALUES(?,?,?,?,?,?)""",
            (
                no, qty, "out",
                user["display_name"] or user["username"],
                belong, f.get("remark", ""),
            ),
        )
        db.commit()
        log_action("领用出库", no, f"-{qty} 归属:{belong}")
        return jsonify(ok=True, redirect=url_for("mobile.done", msg="出库成功"))

    # GET
    material = None
    no = request.args.get("materialNo", "").strip()
    if no:
        material = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()

    types_rows = db.execute("SELECT * FROM materials_type ORDER BY type_no").fetchall()
    types = [dict(t) for t in types_rows]

    return render_template(
        "mobile/outbound.html",
        material=dict(material) if material else None,
        belongs=BELONG_OPTIONS,
        types=types,
    )


# ============================================================
# 数据盘点
# ============================================================
@mobile_bp.route("/stocktake", methods=["GET", "POST"])
@login_required("mobile")
def stocktake():
    db = get_db()

    if request.method == "POST":
        f = request.form
        no = f["material_no"].strip()
        after = int(f.get("after_qty") or 0)

        row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
        if not row:
            return jsonify(ok=False, msg="物料不存在")

        before = row["quantity"]
        db.execute(
            "UPDATE materials SET quantity=?, updated_at=datetime('now','localtime') WHERE material_no=?",
            (after, no),
        )
        user = session["user"]
        db.execute(
            """INSERT INTO stocktake_records(material_no,before_qty,after_qty,operator,remark)
               VALUES(?,?,?,?,?)""",
            (no, before, after, user["display_name"] or user["username"], f.get("remark", "")),
        )
        db.commit()
        log_action("数据盘点", no, f"{before} → {after}")
        return jsonify(ok=True, redirect=url_for("mobile.done", msg="盘点成功"))

    material = None
    no = request.args.get("materialNo", "").strip()
    if no:
        material = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()

    return render_template(
        "mobile/stocktake.html",
        material=dict(material) if material else None,
    )


# ============================================================
# 完成
# ============================================================
@mobile_bp.route("/done")
@login_required("mobile")
def done():
    back = request.args.get("back", "")
    return render_template("mobile/done.html", msg=request.args.get("msg", "操作成功"), back=back)