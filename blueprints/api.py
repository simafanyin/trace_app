from flask import Blueprint, jsonify, send_file, request
from io import BytesIO
import qrcode
from db import get_db
from config import Config
from datetime import date, timedelta
from calendar import monthrange

api_bp = Blueprint("api", __name__)


@api_bp.route("/material/<no>")
def material(no):
    db = get_db()
    row = db.execute("SELECT * FROM materials WHERE material_no=?", (no,)).fetchone()
    if not row:
        return jsonify(ok=False, msg="not found")
    return jsonify(ok=True, data=dict(row))


@api_bp.route("/materials")
def materials():
    db = get_db()
    rows = db.execute("SELECT * FROM materials ORDER BY material_no").fetchall()
    return jsonify(ok=True, data=[dict(r) for r in rows])

@api_bp.route("/qrcode/<no>")
def qrcode_img(no):
    url = f"http://{Config.MY_IP}:{Config.PORT}/m/scan?materialNo={no}"
    img = qrcode.make(url)
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return send_file(bio, mimetype="image/png")

@api_bp.route("/stats/frequency")
def stats_frequency():
    db = get_db()
    rows = db.execute("""
        SELECT material_no, COUNT(*) as cnt
        FROM in_out_bound_records
        WHERE in_or_out='out'
        GROUP BY material_no
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()
    return jsonify(ok=True,
                   labels=[r["material_no"] for r in rows],
                   values=[r["cnt"] for r in rows])

# ============================================================
# 数据统计 API
# ============================================================
def _parse_month(s):
    try:
        y, m = s.split("-")
        return int(y), int(m)
    except Exception:
        return None


def _month_range(start_str, end_str):
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


@api_bp.route("/stats/daily_by_belong")
def stats_daily_by_belong():
    """折线图：按天 + 按归属"""
    db = get_db()
    no      = request.args.get("no", "").strip()
    name    = request.args.get("name", "").strip()
    start_s = request.args.get("start_month", "").strip()
    end_s   = request.args.get("end_month", "").strip()

    start, end = _month_range(start_s, end_s)
    if not start or not end:
        return jsonify(ok=False, msg="请选择开始月份和结束月份")
    if start > end:
        return jsonify(ok=False, msg="开始月份不能晚于结束月份")

    where  = ["r.in_or_out = 'out'", "date(r.created_at) BETWEEN ? AND ?"]
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
                   COALESCE(r.belong, '其他') AS belong,
                   SUM(r.quantity) AS qty
            FROM in_out_bound_records r
            LEFT JOIN materials m ON m.material_no = r.material_no
            {where_sql}
            GROUP BY d, belong
            ORDER BY d""",
        params,
    ).fetchall()

    days = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)

    belongs = sorted({r["belong"] for r in rows})

    series = []
    for b in belongs:
        by_day = {r["d"]: r["qty"] for r in rows if r["belong"] == b}
        data = [int(by_day.get(d, 0)) for d in days]
        series.append({"belong": b, "data": data})

    return jsonify(ok=True, labels=days, series=series)


@api_bp.route("/stats/pie_by_belong")
def stats_pie_by_belong():
    """饼图：某物料在时间段内各归属的领用次数"""
    db = get_db()
    no      = request.args.get("no", "").strip()
    start_s = request.args.get("start_month", "").strip()
    end_s   = request.args.get("end_month", "").strip()

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

    return jsonify(
        ok=True,
        labels=[r["belong"] for r in rows],
        values=[int(r["cnt"]) for r in rows],
    )


@api_bp.route("/stats/day_detail")
def stats_day_detail():
    """某天领用明细，按归属分组"""
    db = get_db()
    day  = request.args.get("date", "").strip()
    no   = request.args.get("no", "").strip()
    name = request.args.get("name", "").strip()

    if not day:
        return jsonify(ok=False, msg="请指定日期")

    where  = ["r.in_or_out = 'out'", "date(r.created_at) = ?"]
    params = [day]

    if no:
        where.append("r.material_no LIKE ?")
        params.append(f"%{no}%")
    if name:
        where.append("m.name LIKE ?")
        params.append(f"%{name}%")

    where_sql = "WHERE " + " AND ".join(where)

    rows = db.execute(
        f"""SELECT r.material_no,
                   m.name AS material_name,
                   r.quantity,
                   COALESCE(r.belong, '其他') AS belong,
                   r.operator,
                   r.remark,
                   r.created_at
            FROM in_out_bound_records r
            LEFT JOIN materials m ON m.material_no = r.material_no
            {where_sql}
            ORDER BY r.belong, r.id DESC""",
        params,
    ).fetchall()

    groups_map = {}
    for r in rows:
        b = r["belong"] or "其他"
        g = groups_map.setdefault(b, {
            "belong": b, "rows_count": 0, "qty_sum": 0, "items": [],
        })
        g["rows_count"] += 1
        g["qty_sum"]   += int(r["quantity"] or 0)
        g["items"].append({
            "material_no":   r["material_no"],
            "material_name": r["material_name"] or "",
            "quantity":      int(r["quantity"] or 0),
            "operator":      r["operator"] or "",
            "remark":        r["remark"] or "",
            "created_at":    r["created_at"],
        })

    groups = sorted(groups_map.values(), key=lambda x: -x["qty_sum"])

    return jsonify(
        ok=True,
        date=day,
        total_rows=sum(g["rows_count"] for g in groups),
        total_qty=sum(g["qty_sum"] for g in groups),
        groups=groups,
    )
    db = get_db()
    no      = request.args.get("no", "").strip()
    start_s = request.args.get("start_month", "").strip()
    end_s   = request.args.get("end_month", "").strip()

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