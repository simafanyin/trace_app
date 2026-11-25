from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, send_file, jsonify)
from io import BytesIO
from datetime import datetime
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
import qrcode

from db import get_db

from utils import (hash_password, verify_password, login_required,
                   log_action, has_perm, get_user_perms, save_user_perms,
                   require_perm, PERM_MODULES, PERM_MODULE_NAMES)


# 物料图片处理
import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename
from config import Config

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

BELONG_OPTIONS = ["方一", "方二", "方三", "方向盘", "踏板", "基座", "支架", "其他"]

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


# ============================================================
# 图片工具
# ============================================================
def _allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save_image(file_storage, material_no: str):
    """保存原图 + 缩略图，返回 (orig_rel, thumb_rel)，失败返回 (None, None)"""
    if not file_storage or not file_storage.filename:
        return None, None
    if not _allowed_image(file_storage.filename):
        return None, None

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    safe_no = secure_filename(material_no) or "mat"
    fname = f"{safe_no}_{uuid.uuid4().hex[:8]}.{ext}"

    orig_path  = os.path.join(Config.UPLOAD_ORIGINAL, fname)
    thumb_path = os.path.join(Config.UPLOAD_THUMB, fname)

    os.makedirs(Config.UPLOAD_ORIGINAL, exist_ok=True)
    os.makedirs(Config.UPLOAD_THUMB, exist_ok=True)

    file_storage.save(orig_path)

    try:
        im = Image.open(orig_path).convert("RGB")
        w, h = im.size
        ratio = Config.THUMB_WIDTH / max(w, h)
        if ratio < 1:
            im = im.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        im.save(thumb_path, quality=82, optimize=True)
    except Exception:
        thumb_path = orig_path

    orig_rel  = f"uploads/original/{fname}"
    thumb_rel = f"uploads/thumb/{fname}" if thumb_path != orig_path else orig_rel
    return orig_rel, thumb_rel


def _delete_image(original_rel: str, thumb_rel: str = None):
    for rel in filter(None, [original_rel, thumb_rel]):
        path = os.path.join(Config.BASE_DIR, "static", rel)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass


# ============================================================
# 登录 / 登出
# ============================================================
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("user_name", "").strip()
        p = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE user_name=?", (u,)).fetchone()
        if row and row["role"] == "admin" and verify_password(p, row["password_hash"]):
            session["user"] = {
                "id": row["id"],
                "username": row["user_name"],
                "role": row["role"],
                "display_name": row["display_name"],
            }
            log_action("登录", u)
            return redirect(url_for("admin.materials"))
        flash("账号或密码错误")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    log_action("登出")
    session.pop("user", None)
    return redirect(url_for("admin.login"))


# ============================================================
# 物料管理
# ============================================================
@admin_bp.route("/materials")
@login_required("admin")
@require_perm("materials", "view")
def materials():
    db = get_db()
    kw_no = request.args.get("no", "").strip()
    kw_name = request.args.get("name", "").strip()
    kw_cat0 = request.args.get("category_0", "").strip()
    kw_cat = request.args.get("category", "").strip()
    page = int(request.args.get("page", 1))
    size = 30
    sort = request.args.get("sort", "material_no")
    order = request.args.get("order", "asc")
    if sort not in ("material_no", "name", "quantity", "updated_at", "category"):
        sort = "material_no"
    if order not in ("asc", "desc"):
        order = "asc"

    where, params = [], []
    if kw_no:
        where.append("material_no LIKE ?")
        params.append(f"%{kw_no}%")
    if kw_name:
        where.append("name LIKE ?")
        params.append(f"%{kw_name}%")
    if kw_cat0:
        where.append("category_0 = ?")
        params.append(kw_cat0)
    if kw_cat:
        where.append("category = ?")
        params.append(kw_cat)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM materials {where_sql}", params
    ).fetchone()[0]

    rows = db.execute(
        f"SELECT * FROM materials {where_sql} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [size, (page - 1) * size],
    ).fetchall()

    types_rows = db.execute(
        "SELECT * FROM materials_type ORDER BY type_no"
    ).fetchall()

    materials = [dict(r) for r in rows]
    types = [dict(t) for t in types_rows]

    return render_template(
        "admin/materials.html",
        materials=materials,
        types=types,
        belongs=BELONG_OPTIONS,
        total=total,
        page=page,
        size=size,
        kw={"no": kw_no, "name": kw_name, "category_0": kw_cat0, "category": kw_cat},
        sort=sort,
        order=order,
    )

@admin_bp.route("/materials/<no>/detail")
@login_required("admin")
@require_perm("materials", "view")
def material_detail(no):
    db = get_db()
    row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="物料不存在")
    data = dict(row)
    # 补全图片 URL（前端直接用）
    data["image_url"]       = f"/static/{data['image']}" if data.get("image") else None
    data["image_thumb_url"] = f"/static/{data['image_thumb'] or data['image']}" if (data.get("image") or data.get("image_thumb")) else None
    return jsonify(ok=True, data=data)

@admin_bp.route("/materials/new", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_new():
    f = request.form
    no = f["material_no"].strip()
    db = get_db()

    img_file = request.files.get("image")
    orig_rel, thumb_rel = _save_image(img_file, no)
    warn_qty_raw = f.get("warn_qty", "").strip()
    warn_qty = int(warn_qty_raw) if warn_qty_raw else None

    try:
        db.execute(
            """INSERT INTO materials(material_no,name,spec,category_0,category,unit,remark,sku,quantity,warn_qty,image,image_thumb,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))""",
            (
                no,
                f["name"].strip(),
                f.get("spec", ""),
                f.get("category_0", ""),
                f.get("category", ""),
                f.get("unit", ""),
                f.get("remark", ""),
                f.get("sku", ""),
                int(f.get("quantity") or 0),
                warn_qty,
                orig_rel,
                thumb_rel,
            ),
        )
        db.commit()
        log_action("新增物料", no, "含图片" if orig_rel else "无图片")
        return jsonify(ok=True)
    except Exception as e:
        _delete_image(orig_rel, thumb_rel)
        return jsonify(ok=False, msg=str(e))


@admin_bp.route("/materials/<no>/edit", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_edit(no):
    """编辑物料，不改数量"""
    f = request.form
    db = get_db()

    old = db.execute(
        "SELECT image, image_thumb FROM materials WHERE material_no=?", (no,)
    ).fetchone()
    old_orig  = old["image"] if old else None
    old_thumb = old["image_thumb"] if old else None

    img_file = request.files.get("image")
    has_new = img_file and img_file.filename
    remove_flag = f.get("remove_image") == "1"
    warn_qty_raw = f.get("warn_qty", "").strip()
    warn_qty = int(warn_qty_raw) if warn_qty_raw else None

    if has_new:
        new_orig, new_thumb = _save_image(img_file, no)
        final_orig, final_thumb = new_orig, new_thumb
    elif remove_flag:
        final_orig, final_thumb = None, None
    else:
        final_orig, final_thumb = old_orig, old_thumb

    db.execute(
        """UPDATE materials SET name=?,spec=?,category_0=?,category=?,unit=?,remark=?,sku=?,
       warn_qty=?, image=?, image_thumb=?, updated_at=datetime('now','localtime')
       WHERE material_no=?""",
        (
            f["name"],
            f.get("spec", ""),
            f.get("category_0", ""),
            f.get("category", ""),
            f.get("unit", ""),
            f.get("remark", ""),
            f.get("sku", ""),
            warn_qty,
            final_orig,
            final_thumb,
            no,
        ),
    )
    db.commit()

    if old_orig and (old_orig != final_orig or old_thumb != final_thumb):
        _delete_image(old_orig, old_thumb)

    log_action("编辑物料", no,
               "更新图片" if has_new else ("删除图片" if remove_flag else ""))
    return jsonify(ok=True)


@admin_bp.route("/materials/<no>/delete", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_delete(no):
    db = get_db()
    row = db.execute(
        "SELECT image, image_thumb FROM materials WHERE material_no=?", (no,)
    ).fetchone()
    db.execute("DELETE FROM materials WHERE material_no=?", (no,))
    db.commit()

    if row:
        _delete_image(row["image"], row["image_thumb"])

    log_action("删除物料", no)
    return jsonify(ok=True)


@admin_bp.route("/materials/<no>/image", methods=["DELETE", "POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_image_delete(no):
    db = get_db()
    row = db.execute("SELECT image, image_thumb FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="物料不存在")
    if row["image"] or row["image_thumb"]:
        _delete_image(row["image"], row["image_thumb"])
    db.execute("UPDATE materials SET image=NULL, image_thumb=NULL WHERE material_no=?", (no,))
    db.commit()
    log_action("删除物料图片", no)
    return jsonify(ok=True)


# ============================================================
# 入库 / 出库 / 盘点（后台管理端，逻辑与手机端一致）
# ============================================================
@admin_bp.route("/materials/<no>/inbound", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_inbound(no):
    f = request.form
    qty = int(f.get("quantity") or 0)
    if qty <= 0:
        return jsonify(ok=False, msg="数量必须大于 0")

    db = get_db()
    row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="物料不存在")

    db.execute(
        """UPDATE materials SET quantity=quantity+?, updated_at=datetime('now','localtime')
           WHERE material_no=?""",
        (qty, no),
    )
    user = session["user"]
    db.execute(
        """INSERT INTO in_out_bound_records(material_no,quantity,in_or_out,operator,remark)
           VALUES(?,?,?,?,?)""",
        (no, qty, "in", user["display_name"] or user["username"], f.get("remark", "")),
    )
    db.commit()
    log_action("来料入库", no, f"+{qty}")
    return jsonify(ok=True, msg=f"入库成功 +{qty}")


@admin_bp.route("/materials/<no>/outbound", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_outbound(no):
    f = request.form
    qty = int(f.get("quantity") or 0)
    belong = f.get("belong", "").strip()

    if not belong:
        return jsonify(ok=False, msg="请选择归属")
    if belong not in BELONG_OPTIONS:
        return jsonify(ok=False, msg="归属不合法")

    db = get_db()
    row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="物料不存在")
    if qty <= 0 or qty > row["quantity"]:
        return jsonify(ok=False, msg="数量不合法或库存不足")

    db.execute(
        """UPDATE materials SET quantity=quantity-?, updated_at=datetime('now','localtime')
           WHERE material_no=?""",
        (qty, no),
    )
    user = session["user"]
    db.execute(
        """INSERT INTO in_out_bound_records(material_no,quantity,in_or_out,operator,belong,remark)
           VALUES(?,?,?,?,?,?)""",
        (no, qty, "out", user["display_name"] or user["username"], belong, f.get("remark", "")),
    )
    db.commit()
    log_action("领用出库", no, f"-{qty} 归属:{belong}")
    return jsonify(ok=True, msg=f"出库成功 -{qty}")


@admin_bp.route("/materials/<no>/stocktake", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def material_stocktake(no):
    f = request.form
    after = int(f.get("after_qty") or 0)
    if after < 0:
        return jsonify(ok=False, msg="盘点数量不能为负")

    db = get_db()
    row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="物料不存在")

    before = row["quantity"]
    db.execute(
        """UPDATE materials SET quantity=?, updated_at=datetime('now','localtime')
           WHERE material_no=?""",
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
    return jsonify(ok=True, msg=f"盘点成功 {before} → {after}")


# ============================================================
# 导入 / 导出 / 模板
# ============================================================
@admin_bp.route("/materials/export")
@login_required("admin")
@require_perm("materials", "view")
def materials_export():
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from PIL import Image as PILImage
    from io import BytesIO as _BIO

    db = get_db()
    rows = db.execute("SELECT * FROM materials ORDER BY material_no").fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "物料"

    headers = ["物料号", "物料名称", "规格型号", "大类名称", "分类名称", "单位", "备注", "SKU", "库存", "图片"]
    ws.append(headers)

    col_widths = {"A": 16, "B": 20, "C": 16, "D": 16, "E": 12,
                  "F": 8, "G": 20, "H": 18, "I": 10, "j": 18}
    for col, w in col_widths.items():
        ws.column_dimensions[col].width = w

    DISPLAY_W, DISPLAY_H = 80, 80

    for idx, r in enumerate(rows, start=2):
        ws.cell(row=idx, column=1, value=r["material_no"])
        ws.cell(row=idx, column=2, value=r["name"])
        ws.cell(row=idx, column=3, value=r["spec"])
        ws.cell(row=idx, column=4, value=r["category_0"])
        ws.cell(row=idx, column=5, value=r["category"])
        ws.cell(row=idx, column=6, value=r["unit"])
        ws.cell(row=idx, column=7, value=r["remark"])
        ws.cell(row=idx, column=8, value=r["sku"])
        ws.cell(row=idx, column=9, value=r["quantity"])
        ws.row_dimensions[idx].height = 65

        img_rel = r["image"] or r["image_thumb"]
        if img_rel:
            img_path = os.path.join(Config.BASE_DIR, "static", img_rel)
            if os.path.isfile(img_path):
                try:
                    pil = PILImage.open(img_path)
                    if getattr(pil, "is_animated", False):
                        pil.seek(0)
                    pil = pil.convert("RGB")
                    pil.thumbnail((DISPLAY_W * 2, DISPLAY_H * 2), PILImage.LANCZOS)

                    bio_img = _BIO()
                    pil.save(bio_img, format="PNG")
                    bio_img.seek(0)

                    xl_img = XLImage(bio_img)          # ← BytesIO，扩展名固定为 png
                    xl_img.width  = DISPLAY_W
                    xl_img.height = DISPLAY_H
                    ws.add_image(xl_img, f"J{idx}")
                except Exception as e:
                    ws.cell(row=idx, column=10, value=f"[图片无法嵌入] {type(e).__name__}")
            else:
                ws.cell(row=idx, column=10, value="[文件不存在]")
        else:
            ws.cell(row=idx, column=10, value="无")

    ws.freeze_panes = "A2"

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    log_action("导出 Excel")
    return send_file(
        bio,
        as_attachment=True,
        download_name="materials.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/materials/template")
@login_required("admin")
@require_perm("materials", "view")
def materials_template():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "模板"
    ws.append(["物料号", "物料名称", "规格型号", "大类名称", "分类名称", "单位", "备注", "SKU", "库存"])
    ws.append(["M001", "示例螺丝", "M4*10", "工具", "胶水", "个", "", "SKU-001", 0])
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(
        bio,
        as_attachment=True,
        download_name="template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/materials/import", methods=["POST"])
@login_required("admin")
@require_perm("materials", "edit")
def materials_import():
    from openpyxl import load_workbook
    file = request.files.get("file")
    if not file or not file.filename.endswith(".xlsx"):
        return jsonify(ok=False, msg="请上传 .xlsx 文件")
    wb = load_workbook(file)
    ws = wb.active
    db = get_db()
    n_add = n_upd = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        vals = list(row) + [None] * 9
        no, name, spec, cat0, cat, unit, remark, sku, qty = vals[:9]   # ← 8 列
        qty = int(qty or 0)
        exist = db.execute("SELECT 1 FROM materials WHERE material_no=?", (str(no),)).fetchone()
        if exist:
            db.execute(
                """UPDATE materials SET name=?,spec=?,category_0=?,category=?,unit=?,remark=?,sku=?,quantity=?,
                updated_at=datetime('now','localtime') WHERE material_no=?""",
                (name, spec or "", cat0 or "", cat or "", unit or "", remark or "", sku or "", qty, str(no)),
            )
            n_upd += 1
        else:
            db.execute(
                """INSERT INTO materials(material_no,name,spec,category_0, category,unit,remark,sku,quantity)
                VALUES(?,?,?,?,?,?,?,?)""",
                (str(no), name or "", spec or "", cat0 or "", cat or "", unit or "", remark or "", sku or "", qty),
            )
            n_add += 1
    db.commit()
    log_action("导入物料", detail=f"新增{n_add} 更新{n_upd}")
    return jsonify(ok=True, msg=f"新增 {n_add} 条，更新 {n_upd} 条")


# ============================================================
# 物料类别
# ============================================================
@admin_bp.route("/types")
@login_required("admin")
@require_perm("types", "view")
def types():
    db = get_db()
    kw_no = request.args.get("no", "").strip()
    kw_cat = request.args.get("category", "").strip()

    where, params = [], []
    if kw_no:
        where.append("type_no LIKE ?")
        params.append(f"%{kw_no}%")
    if kw_cat:
        where.append("category LIKE ?")
        params.append(f"%{kw_cat}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        f"SELECT * FROM materials_type {where_sql} ORDER BY type_no",
        params,
    ).fetchall()

    types = [dict(r) for r in rows]
    return render_template(
        "admin/types.html",
        types=types,
        kw={"no": kw_no, "category": kw_cat},
    )


@admin_bp.route("/types/new", methods=["POST"])
@login_required("admin")
@require_perm("types", "edit")
def type_new():
    f = request.form
    db = get_db()
    tid = f.get("type_id") or f"T{f['type_no']}"
    db.execute(
        "INSERT INTO materials_type(type_id,type_no,category) VALUES(?,?,?)",
        (tid, f["type_no"], f["category"]),
    )
    db.commit()
    log_action("新增分类", f["type_no"])
    return jsonify(ok=True)


@admin_bp.route("/types/<tid>/edit", methods=["POST"])
@login_required("admin")
@require_perm("types", "edit")
def type_edit(tid):
    f = request.form
    db = get_db()
    db.execute(
        "UPDATE materials_type SET type_no=?, category=? WHERE type_id=?",
        (f["type_no"], f["category"], tid),
    )
    db.commit()
    log_action("编辑分类", tid)
    return jsonify(ok=True)


@admin_bp.route("/types/<tid>/delete", methods=["POST"])
@login_required("admin")
@require_perm("types", "edit")
def type_delete(tid):
    db = get_db()
    db.execute("DELETE FROM materials_type WHERE type_id=?", (tid,))
    db.commit()
    log_action("删除分类", tid)
    return jsonify(ok=True)


# ============================================================
# 用户管理
# ============================================================
@admin_bp.route("/users")
@login_required("admin")
@require_perm("users", "view")
def users():
    db = get_db()
    current = session.get("user") or {}
    is_super = current.get("username") == "admin"

    kw_u = request.args.get("u", "").strip()
    kw_d = request.args.get("d", "").strip()
    page = int(request.args.get("page", 1))
    size = 20

    where, params = [], []

    # 非系统管理员：强制只看自己
    if not is_super:
        where.append("id = ?")
        params.append(current["id"])

    if kw_u:
        where.append("user_name LIKE ?")
        params.append(f"%{kw_u}%")
    if kw_d:
        where.append("display_name LIKE ?")
        params.append(f"%{kw_d}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM users {where_sql}", params).fetchone()[0]

    rows = db.execute(
        f"SELECT * FROM users {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [size, (page - 1) * size],
    ).fetchall()

    return render_template(
        "admin/users.html",
        users=rows,
        total=total,
        page=page,
        size=size,
        kw={"u": kw_u, "d": kw_d},
        is_super_admin=is_super,       # ← 传给模板控制 UI
    )

@admin_bp.route("/users/new", methods=["POST"])
@login_required("admin")
@require_perm("users", "edit")
def user_new():
    current = session.get("user") or {}
    if current.get("username") != "admin":
        return jsonify(ok=False, msg="只有系统管理员可新增用户")

    f = request.form
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users(user_name,password_hash,role,display_name) VALUES(?,?,?,?)",
            (f["user_name"], hash_password(f["password"]),
             f.get("role", "mobile"), f.get("display_name", "")),
        )
        uid = cur.lastrowid
        db.commit()

        from utils import PERM_MODULES, save_user_perms
        default = {m: {"view": True, "edit": False} for m in PERM_MODULES}
        save_user_perms(uid, default)

        log_action("新增用户", f["user_name"])
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, msg=str(e))


@admin_bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required("admin")
@require_perm("users", "edit")
def user_delete(uid):
    current = session.get("user") or {}
    is_super = current.get("username") == "admin"

    if not is_super:
        return jsonify(ok=False, msg="只有系统管理员可删除账号")

    db = get_db()
    row = db.execute("SELECT user_name, role FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="用户不存在")

    if row["user_name"] == "admin":
        return jsonify(ok=False, msg="系统管理员 admin 不可删除")
    if current.get("id") == uid:
        return jsonify(ok=False, msg="不能删除自己")

    db.execute("DELETE FROM permissions WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    log_action("删除用户", row["user_name"])
    return jsonify(ok=True)


@admin_bp.route("/users/<int:uid>/password", methods=["POST"])
@login_required("admin")              # 只要求登录，不强制 users/edit
def user_password(uid):
    current = session.get("user") or {}
    is_super = current.get("username") == "admin"

    # 非系统管理员：只能改自己
    if not is_super and current.get("id") != uid:
        return jsonify(ok=False, msg="只能修改自己的密码")

    pwd = request.form.get("password", "")
    if not pwd:
        return jsonify(ok=False, msg="密码不能为空")

    db = get_db()
    row = db.execute("SELECT user_name FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="用户不存在")

    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(pwd), uid))
    db.commit()

    if current.get("id") == uid:
        log_action("修改自己密码", row["user_name"])
    else:
        log_action("修改密码", row["user_name"])

    return jsonify(ok=True)

@admin_bp.route("/users/<int:uid>/perms", methods=["GET"])
@login_required("admin")
@require_perm("users", "view")
def user_perms_get(uid):
    current = session.get("user") or {}
    if current.get("username") != "admin":
        return jsonify(ok=False, msg="只有系统管理员可查看权限")
    db = get_db()
    row = db.execute("SELECT user_name, display_name FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="用户不存在")

    perms = get_user_perms(uid)
    return jsonify(
        ok=True,
        user={"id": uid, "user_name": row["user_name"], "display_name": row["display_name"]},
        perms=perms,
        modules=[{"key": k, "name": PERM_MODULE_NAMES[k], "actions": sorted(list(v))}
                 for k, v in PERM_MODULES.items()],
    )


@admin_bp.route("/users/<int:uid>/perms", methods=["POST"])
@login_required("admin")
@require_perm("users", "edit")
def user_perms_save(uid):
    current = session.get("user") or {}
    if current.get("username") != "admin":
        return jsonify(ok=False, msg="只有系统管理员可查看权限")
    db = get_db()
    row = db.execute("SELECT user_name FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="用户不存在")

    if row["user_name"] == "admin":
        return jsonify(ok=False, msg="admin 账号拥有全部权限，不可修改")

    data = request.get_json(silent=True) or {}
    perms = data.get("perms", {})
    # 规整结构
    clean = {}
    for module in PERM_MODULES:
        p = perms.get(module, {}) or {}
        clean[module] = {
            "view": bool(p.get("view")),
            "edit": bool(p.get("edit")),
        }
    save_user_perms(uid, clean)
    log_action("修改用户权限", row["user_name"], str(clean))
    return jsonify(ok=True, msg="权限已保存")


# ============================================================
# 出入库记录
# ============================================================
@admin_bp.route("/records")
@login_required("admin")
@require_perm("records", "view")
def records():
    db = get_db()
    page = int(request.args.get("page", 1))
    size = 50

    kw_no     = request.args.get("no", "").strip()
    kw_name   = request.args.get("name", "").strip()
    kw_belong = request.args.get("belong", "").strip()

    where, params = [], []
    if kw_no:
        where.append("r.material_no LIKE ?")
        params.append(f"%{kw_no}%")
    if kw_name:
        where.append("m.name LIKE ?")
        params.append(f"%{kw_name}%")
    if kw_belong:
        where.append("r.belong = ?")
        params.append(kw_belong)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(
        f"""SELECT COUNT(*) FROM in_out_bound_records r
            LEFT JOIN materials m ON m.material_no = r.material_no
            {where_sql}""",
        params,
    ).fetchone()[0]

    rows = db.execute(
        f"""SELECT r.*, m.name FROM in_out_bound_records r
            LEFT JOIN materials m ON m.material_no = r.material_no
            {where_sql}
            ORDER BY r.id DESC LIMIT ? OFFSET ?""",
        params + [size, (page - 1) * size],
    ).fetchall()

    return render_template(
        "admin/records.html",
        records=rows,
        belongs=BELONG_OPTIONS,
        total=total,
        page=page,
        size=size,
        kw={"no": kw_no, "name": kw_name, "belong": kw_belong},
    )


# ============================================================
# 二维码
# ============================================================
@admin_bp.route("/qrcodes")
@login_required("admin")
@require_perm("qrcodes", "view")
def qrcodes():
    db = get_db()
    kw_no   = request.args.get("no", "").strip()
    kw_name = request.args.get("name", "").strip()

    where, params = [], []
    if kw_no:
        where.append("material_no LIKE ?")
        params.append(f"%{kw_no}%")
    if kw_name:
        where.append("name LIKE ?")
        params.append(f"%{kw_name}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        f"SELECT material_no, name FROM materials {where_sql} ORDER BY material_no",
        params,
    ).fetchall()

    return render_template(
        "admin/qrcodes.html",
        materials=rows,
        kw={"no": kw_no, "name": kw_name},
        total=len(rows),
    )

@admin_bp.route("/qrcodes/download")
@login_required("admin")
@require_perm("qrcodes", "view")
def qrcodes_download():
    db = get_db()
    kw_no   = request.args.get("no", "").strip()
    kw_name = request.args.get("name", "").strip()

    where, params = [], []
    if kw_no:
        where.append("material_no LIKE ?")
        params.append(f"%{kw_no}%")
    if kw_name:
        where.append("name LIKE ?")
        params.append(f"%{kw_name}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        f"SELECT material_no, name FROM materials {where_sql} ORDER BY material_no",
        params,
    ).fetchall()

    if not rows:
        return jsonify(ok=False, msg="没有物料可导出")

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(1.5)
        section.right_margin = Cm(1.5)

    title = doc.add_heading("物料二维码", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    COLS = 3
    total = len(rows)
    table_rows = (total + COLS - 1) // COLS

    table = doc.add_table(rows=table_rows * 2, cols=COLS)
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    base_url = f"http://{Config.MY_IP}:{Config.PORT}/m/scan?materialNo="

    for idx, r in enumerate(rows):
        row_group = idx // COLS
        col       = idx % COLS

        img_cell = table.cell(row_group * 2, col)
        txt_cell = table.cell(row_group * 2 + 1, col)

        url = base_url + str(r["material_no"])
        img = qrcode.make(url)
        bio = BytesIO()
        img.save(bio, "PNG")
        bio.seek(0)

        img_para = img_cell.paragraphs[0]
        img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = img_para.add_run()
        run.add_picture(bio, width=Cm(3.5), height=Cm(3.5))

        txt_para = txt_cell.paragraphs[0]
        txt_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_no = txt_para.add_run(str(r["material_no"]))
        run_no.font.size = Pt(10)
        run_no.font.bold = True
        run_no.font.name = "微软雅黑"
        run_no._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

        txt_para.add_run("\n")
        run_name = txt_para.add_run(str(r["name"] or ""))
        run_name.font.size = Pt(9)
        run_name.font.name = "微软雅黑"
        run_name._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    bio_out = BytesIO()
    doc.save(bio_out)
    bio_out.seek(0)

    log_action("导出二维码 Word", detail=f"{total} 条")
    return send_file(
        bio_out,
        as_attachment=True,
        download_name=f"qrcodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ============================================================
# 操作日志
# ============================================================
@admin_bp.route("/logs")
@login_required("admin")
@require_perm("logs", "view")
def logs():
    db = get_db()
    page = int(request.args.get("page", 1))
    size = 50
    kw_u = request.args.get("u", "").strip()

    where, params = [], []
    if kw_u:
        where.append("user_name LIKE ?")
        params.append(f"%{kw_u}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM operation_logs {where_sql}", params
    ).fetchone()[0]

    rows = db.execute(
        f"SELECT * FROM operation_logs {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [size, (page - 1) * size],
    ).fetchall()

    return render_template(
        "admin/logs.html",
        logs=rows,
        total=total,
        page=page,
        size=size,
        kw={"u": kw_u},
    )


# ============================================================
# 数据统计
# ============================================================
@admin_bp.route("/stats")
@login_required("admin")
@require_perm("stats", "view")
def stats():
    return render_template("admin/stats.html")

# ============================================================
# 数据统计 API
# ============================================================
from calendar import monthrange
from datetime import date

def _parse_month(s):
    """'2025-01' → (year, month) 或 None"""
    try:
        y, m = s.split("-")
        return int(y), int(m)
    except Exception:
        return None


def _month_range(start_str, end_str):
    """
    返回 (start_date, end_date_inclusive)，
    如 ('2025-01', '2025-03') → (date(2025,1,1), date(2025,3,31))
    """
    s = _parse_month(start_str)
    e = _parse_month(end_str)
    if not s or not e:
        return None, None
    sy, sm = s
    ey, em = e
    start = date(sy, sm, 1)
    last_day = monthrange(ey, em)[1]
    end = date(ey, em, last_day)
    return start, end


@admin_bp.route("/api/stats/daily_by_belong")
@login_required("admin")
@require_perm("stats", "view")
def stats_daily_by_belong():
    """
    折线图数据：按天聚合，按归属分组
    参数：no, name, start_month, end_month
    返回：
      labels: ['2025-01-01', '2025-01-02', ...]
      series: [{ belong: '方一', data: [0, 2, 1, ...] }, ...]
    """
    db = get_db()
    no     = request.args.get("no", "").strip()
    name   = request.args.get("name", "").strip()
    start_s= request.args.get("start_month", "").strip()
    end_s  = request.args.get("end_month", "").strip()

    start, end = _month_range(start_s, end_s)
    if not start or not end:
        return jsonify(ok=False, msg="请选择开始月份和结束月份")
    if start > end:
        return jsonify(ok=False, msg="开始月份不能晚于结束月份")

    where = ["r.in_or_out = 'out'",
             "date(r.created_at) BETWEEN ? AND ?"]
    params = [start.isoformat(), end.isoformat()]

    if no:
        where.append("r.material_no LIKE ?")
        params.append(f"%{no}%")
    if name:
        where.append("m.name LIKE ?")
        params.append(f"%{name}%")

    where_sql = "WHERE " + " AND ".join(where)

    rows = db.execute(
        f"""SELECT date(r.created_at) AS d,
                   COALESCE(r.belong, '其他') AS belong, r.remark,
                   SUM(r.quantity) AS qty
            FROM in_out_bound_records r
            LEFT JOIN materials m ON m.material_no = r.material_no
            {where_sql}
            GROUP BY d, belong
            ORDER BY d""",
        params,
    ).fetchall()

    # 生成完整日期序列
    from datetime import timedelta
    days = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)

    # 收集所有出现过的归属
    belongs = sorted({r["belong"] for r in rows})

    # 构造每个归属的序列
    series = []
    for b in belongs:
        # 该归属每天的 qty
        by_day = {r["d"]: r["qty"] for r in rows if r["belong"] == b}
        data = [int(by_day.get(d, 0)) for d in days]
        series.append({"belong": b, "data": data})

    return jsonify(ok=True, labels=days, series=series)


@admin_bp.route("/api/stats/pie_by_belong")
@login_required("admin")
@require_perm("stats", "view")
def stats_pie_by_belong():
    """
    饼图数据：某物料在时间段内各归属的领用次数
    参数：no（必填）, start_month, end_month
    """
    db = get_db()
    no     = request.args.get("no", "").strip()
    start_s= request.args.get("start_month", "").strip()
    end_s  = request.args.get("end_month", "").strip()

    if not no:
        return jsonify(ok=False, msg="请指定物料号")
    start, end = _month_range(start_s, end_s)
    if not start or not end:
        return jsonify(ok=False, msg="请选择开始月份和结束月份")

    rows = db.execute(
        """SELECT COALESCE(belong, '其他') AS belong,
                  COUNT(*) AS cnt
           FROM in_out_bound_records
           WHERE material_no = ?
             AND in_or_out = 'out'
             AND date(created_at) BETWEEN ? AND ?
           GROUP BY belong
           ORDER BY cnt DESC""",
        (no, start.isoformat(), end.isoformat()),
    ).fetchall()

    labels = [r["belong"] for r in rows]
    values = [int(r["cnt"]) for r in rows]
    return jsonify(ok=True, labels=labels, values=values)


@admin_bp.route("/api/stats/materials_search")
@login_required("admin")
@require_perm("stats", "view")
def stats_materials_search():
    """供饼图选物料用：按关键字搜物料号/名称，返回前 20 条"""
    db = get_db()
    kw = request.args.get("kw", "").strip()
    if not kw:
        rows = db.execute(
            "SELECT material_no, name FROM materials ORDER BY material_no LIMIT 20"
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT material_no, name FROM materials
               WHERE material_no LIKE ? OR name LIKE ?
               ORDER BY material_no LIMIT 20""",
            (f"%{kw}%", f"%{kw}%"),
        ).fetchall()
    return jsonify(ok=True, data=[dict(r) for r in rows])