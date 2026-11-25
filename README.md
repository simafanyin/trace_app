# 低值易耗品管理系统 — 产品文档 & 技术规格书

------

# 第一部分：产品文档（PRD）

## 1. 产品概述

### 1.1 产品定位

面向企业 / 仓库 / 车间的**低值易耗品**（螺丝、手套、口罩、文具、工具等）的轻量级库存管理系统。

- **手机端**：现场人员完成入库、领用、盘点、扫码查询
- **后台管理**：管理员统一管理物料、账号、权限、记录、统计
- **部署形态**：局域网单机部署（内网 IP 访问），无需外网

### 1.2 目标用户

| 角色                           | 使用场景                                                   | 入口           |
| :----------------------------- | :--------------------------------------------------------- | :------------- |
| **系统管理员（`admin`）**      | 全局管理：物料、分类、用户、权限、记录、日志、统计、二维码 | `/admin/login` |
| **其他管理员（`admin` 角色）** | 按授权模块管理；人员管理仅看自己、改自己密码               | `/admin/login` |
| **普通员工（`mobile` 角色）**  | 手机端：来料入库、扫码领用、数据盘点、物料查询             | `/m/login`     |

### 1.3 核心价值

- **零成本部署**：Python + SQLite，单机即用，无需数据库服务器
- **手机扫码**：贴在物料上的二维码一扫即达详情，领用/盘点两步完成
- **权限可控**：模块级"查看/编辑"权限，导航与按钮自动联动
- **数据可追溯**：所有出入库/盘点/操作日志留痕，可按天/按人/按归属分析

------

## 2. 功能清单

### 2.1 后台管理（`/admin`）

| 模块            | 功能                                                         | 权限点                              |
| :-------------- | :----------------------------------------------------------- | :---------------------------------- |
| **登录 / 登出** | 账号密码登录，登出记日志                                     | —                                   |
| **物料管理**    | 列表（分页/排序/筛选/缩略图）、新增、编辑、删除、详情、**盘点/入库/出库**弹框、导入/导出 Excel | `materials.view` / `materials.edit` |
| **物料类别**    | 列表、新增、编辑、删除                                       | `types.view` / `types.edit`         |
| **人员管理**    | 列表、新增、删除、改密、**权限设置**                         | `users.view` / `users.edit`         |
| **二维码打印**  | 二维码网格、按物料号/名称查找、**下载 Word**、打印           | `qrcodes.view`                      |
| **出入库记录**  | 列表、按物料号/名称/归属筛选、分页                           | `records.view`                      |
| **操作日志**    | 列表、按操作人筛选、分页                                     | `logs.view`                         |
| **数据统计**    | **折线图**（按天×按归属）、**饼图**（某物料按归属次数）、点击某天查看**按归属分组的明细**（含备注）、开始/结束月份必选 | `stats.view`                        |

### 2.2 手机端（`/m`）

| 模块            | 功能                                                         |
| :-------------- | :----------------------------------------------------------- |
| **登录 / 登出** | 支持 `next` 参数回跳                                         |
| **首页**        | 顶部两按钮（来料入库 / 扫码操作）；物料列表（按物料号升序）+ **名称/物料号搜索**；点击进物料详情 |
| **物料详情**    | 图片缩略图（点击放大）、全部字段、底部"领用出库 / 数据盘点"两按钮 |
| **来料入库**    | 物料号失焦自动带出信息；数量必填；支持新物料创建             |
| **领用出库**    | 物料类别**只读**；数量必填；**归属必填**（方一/方二/方三/方向盘/踏板/基座/支架/其他） |
| **数据盘点**    | 显示当前库存；填盘点后数量；覆盖库存                         |
| **完成页**      | 显示结果消息 + 返回                                          |

### 2.3 权限模型

| 模块       | 支持动作    |
| :--------- | :---------- |
| 物料管理   | view / edit |
| 物料类别   | view / edit |
| 人员管理   | view / edit |
| 二维码打印 | view        |
| 出入库记录 | view        |
| 操作日志   | view        |
| 数据统计   | view        |

- `admin` 账号（`user_name == 'admin'`）→ **所有权限恒为真**，不进库判断
- 其他用户 → 按 `permissions` 表判断
- `edit` 隐含 `view`
- **非系统管理员的人员管理**：只看自己、只能改自己密码、不能删除任何账号
- **系统管理员的人员管理**：可新增/删除 mobile 用户；`admin` 账号和任何 admin 角色**不可删除**

------

## 3. 关键流程

### 3.1 扫码领用

text

```
手机相机扫物料二维码
  → /m/scan?materialNo=xxx
  → 未登录 → 跳 /m/login?next=...
  → 登录成功 → 回详情页
  → 点"领用出库" → /m/outbound?materialNo=xxx
  → 填数量 + 选归属（必填）
  → 提交 → 扣库存 + 写 in_out_bound_records + 写操作日志
  → /m/done → 返回首页
```



### 3.2 月度数据统计

text

```
打开 /admin/stats
  → 默认开始/结束月份 = 当前月
  → 填物料号/名称（可选）→ 点"查询"
  → 折线图：X 轴按天、Y 轴领用数量、多条线按归属
  → 点击折线图某天 → 弹框
     → 顶部：各归属色块（条数 + 数量）
     → 下方：按归属分块的明细表（物料号/名称/数量/操作员/备注/时间）
  → 饼图：输入物料号 → 显示该物料各归属领用次数及占比
```



### 3.3 库存预警

text

```
物料有 warn_qty 且 quantity <= warn_qty
  → 后台列表库存数字红色
  → 详情弹框库存红色
```



### 3.4 权限变更

text

```
admin 登录 → 人员管理 → 点某用户"权限"
  → 勾选模块 view/edit → 保存
  → 该用户重新登录后生效（导航/按钮/接口均按新权限）
```



------

## 4. 页面规范

### 4.1 后台布局

text

```
┌────────┬──────────────────────────────────────┐
│        │ 页面标题（固定）                       │
│  左    │ 查找条件（固定）                       │
│  侧    │ ┌──────────────────────────────────┐ │
│  导    │ │ 表头 sticky（固定）                │ │
│  航    │ ├──────────────────────────────────┤ │
│  固    │ │ 列表内容（唯一滚动区）             │ │
│  定    │ └──────────────────────────────────┘ │
│        │ 分页（固定）                          │
└────────┴──────────────────────────────────────┘
```



- 左导航固定，页面本身不滚，只滚列表区
- 查找条件 sticky，表头 sticky
- 滚动条视觉隐藏，功能保留

### 4.2 手机端布局

- 首页：`body.m-home` flex 布局，100dvh，列表内部滚动
- 详情：图片 + 字段表 + 底部两固定按钮
- 表单：label + input 纵向，输入框 font-size ≥16px（防 iOS 放大）

### 4.3 交互规范

- 所有 AJAX 提交用 `addEventListener('submit', e => { e.preventDefault(); ... })`，**不用** `onsubmit="return asyncFn()"`
- 列表按钮传参用 `data-*`，避免名称含引号导致 JS 报错
- 图片：缩略图 `object-fit: cover`，点击全屏放大
- 长文本（备注/SKU）：`white-space: pre-wrap; word-break: break-all`

------

## 5. 数据备份与运维

### 5.1 备份

bash

```
sqlite3 trace.db ".backup 'backup_$(date +%Y%m%d).db'"
```



### 5.2 定时备份（Linux crontab）

text

```
0 2 * * * cd /path/to/trace_app && sqlite3 trace.db ".backup 'backups/trace_$(date +\%Y\%m\%d).db'"
```



### 5.3 恢复

bash

```
cp backups/trace_20250101.db trace.db
rm -f trace.db-wal trace.db-shm
```



### 5.4 日常检查

| 周期   | 内容                                 |
| :----- | :----------------------------------- |
| 每日   | 服务在线、手机端可登录、扫码可跳转   |
| 每周   | 日志检查、统计查看、磁盘空间         |
| 每月   | Excel 归档、备份验证、账号审查、盘点 |
| 每季度 | 密码策略审查、备份恢复演练           |

------

# 第二部分：技术规格书

## 1. 技术栈

| 层         | 技术                                   | 版本                                         |
| :--------- | :------------------------------------- | :------------------------------------------- |
| 语言       | Python                                 | 3.10+                                        |
| Web 框架   | Flask                                  | 3.x                                          |
| 数据库     | SQLite（WAL 模式）                     | 3.x                                          |
| 模板       | Jinja2                                 | Flask 内置                                   |
| 图表       | Chart.js                               | 4.4（本地 `static/vendor/chart.umd.min.js`） |
| Excel      | openpyxl                               | ≥3.1                                         |
| Word       | python-docx                            | ≥1.1                                         |
| 二维码     | qrcode[pil]                            | ≥7.4                                         |
| 图片处理   | Pillow                                 | 最新                                         |
| 生产服务器 | waitress（Windows）/ gunicorn（Linux） | —                                            |

------

## 2. 目录结构

text

```
trace_app/
├── app.py
├── config.py
├── db.py
├── utils.py
├── requirements.txt
├── trace.db
├── blueprints/
│   ├── __init__.py
│   ├── admin.py
│   ├── mobile.py
│   └── api.py
├── templates/
│   ├── base.html
│   ├── admin/
│   │   ├── _nav.html
│   │   ├── login.html
│   │   ├── materials.html
│   │   ├── types.html
│   │   ├── users.html
│   │   ├── records.html
│   │   ├── qrcodes.html
│   │   ├── logs.html
│   │   ├── stats.html
│   │   └── 403.html
│   └── mobile/
│       ├── login.html
│       ├── home.html
│       ├── scan.html
│       ├── inbound.html
│       ├── outbound.html
│       ├── stocktake.html
│       └── done.html
└── static/
    ├── admin/admin.css
    ├── mobile/mobile.css
    ├── vendor/chart.umd.min.js
    └── uploads/
        ├── original/
        └── thumb/
```



------

## 3. 配置 `config.py`

python

```
import os, socket, logging

def detect_lan_ip() -> str:
    env_ip = os.environ.get("MY_IP", "").strip()
    if env_ip:
        return env_ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith(("127.", "169.254.", "172.17.", "0.0.0.0")):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    PORT = int(os.environ.get("PORT", 5000))
    MY_IP = detect_lan_ip()

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(BASE_DIR, "trace.db")

    UPLOAD_FOLDER   = os.path.join(BASE_DIR, "static", "uploads")
    UPLOAD_ORIGINAL = os.path.join(UPLOAD_FOLDER, "original")
    UPLOAD_THUMB    = os.path.join(UPLOAD_FOLDER, "thumb")
    THUMB_WIDTH     = 120
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    @staticmethod
    def base_url() -> str:
        return f"http://{Config.MY_IP}:{Config.PORT}"
```



------

## 4. 数据库结构

### 4.1 `users`

| 字段          | 类型        | 说明               |
| :------------ | :---------- | :----------------- |
| id            | INTEGER PK  |                    |
| user_name     | TEXT UNIQUE | 登录账号           |
| password_hash | TEXT        | SHA256             |
| role          | TEXT        | `admin` / `mobile` |
| display_name  | TEXT        | 显示名             |
| created_at    | TEXT        |                    |

### 4.2 `materials_type`

| 字段     | 类型        | 说明     |
| :------- | :---------- | :------- |
| type_id  | TEXT PK     |          |
| type_no  | TEXT UNIQUE | 分类编号 |
| category | TEXT        | 分类名称 |

### 4.3 `materials`

| 字段         | 类型    | 说明               |
| :----------- | :------ | :----------------- |
| material_no  | TEXT PK | 物料号             |
| name         | TEXT    |                    |
| spec         | TEXT    |                    |
| category_0   | TEXT    | 耗材， 工具        |
| category     | TEXT    | 详细分类           |
| unit         | TEXT    |                    |
| remark       | TEXT    |                    |
| sku          | TEXT    | 长文本             |
| quantity     | INTEGER | 库存               |
| **warn_qty** | INTEGER | **预警值（可空）** |
| image        | TEXT    | 原图相对路径       |
| image_thumb  | TEXT    | 缩略图相对路径     |
| updated_at   | TEXT    |                    |

### 4.4 `in_out_bound_records`

| 字段        | 说明         |
| :---------- | :----------- |
| id          | INTEGER PK   |
| material_no | 物料号       |
| quantity    | 数量         |
| in_or_out   | `in` / `out` |
| operator    | 操作员       |
| belong      | 归属         |
| remark      | 备注         |
| created_at  | 时间         |

### 4.5 `stocktake_records`

| 字段        | 说明   |
| :---------- | :----- |
| id          |        |
| material_no |        |
| before_qty  | 盘点前 |
| after_qty   | 盘点后 |
| operator    |        |
| remark      |        |
| created_at  |        |

### 4.6 `operation_logs`

| 字段       | 说明 |
| :--------- | :--- |
| id         |      |
| user_name  |      |
| action     | 动作 |
| target     | 对象 |
| detail     | 详情 |
| ip         |      |
| created_at |      |

### 4.7 `permissions`

| 字段                    | 说明                                                     |
| :---------------------- | :------------------------------------------------------- |
| id                      | INTEGER PK                                               |
| user_id                 | INTEGER（FK users.id）                                   |
| module                  | TEXT（materials/types/users/qrcodes/records/logs/stats） |
| can_view                | INTEGER 0/1                                              |
| can_edit                | INTEGER 0/1                                              |
| UNIQUE(user_id, module) |                                                          |

### 4.8 WAL

sql

```
PRAGMA journal_mode=WAL;
```



------

## 5. 路由总表

### 5.1 后台 `admin_bp`（前缀 `/admin`）

| 方法     | 路径                                         | 说明                   | 权限                         |
| :------- | :------------------------------------------- | :--------------------- | :--------------------------- |
| GET/POST | `/login`                                     | 登录                   | —                            |
| GET      | `/logout`                                    | 登出                   | —                            |
| GET      | `/materials`                                 | 物料列表               | materials.view               |
| POST     | `/materials/new`                             | 新增                   | materials.edit               |
| POST     | `/materials/<no>/edit`                       | 编辑（不改数量）       | materials.edit               |
| POST     | `/materials/<no>/delete`                     | 删除                   | materials.edit               |
| POST     | `/materials/<no>/inbound`                    | 入库                   | materials.edit               |
| POST     | `/materials/<no>/outbound`                   | 出库                   | materials.edit               |
| POST     | `/materials/<no>/stocktake`                  | 盘点                   | materials.edit               |
| GET      | `/materials/<no>/detail`                     | 详情 JSON              | materials.view               |
| GET      | `/materials/export`                          | 导出 Excel             | materials.view               |
| GET      | `/materials/template`                        | 下载模板               | materials.view               |
| POST     | `/materials/import`                          | 导入                   | materials.edit               |
| GET      | `/types`                                     | 分类列表               | types.view                   |
| POST     | `/types/new` / `<tid>/edit` / `<tid>/delete` | 分类写操作             | types.edit                   |
| GET      | `/users`                                     | 用户列表               | users.view                   |
| POST     | `/users/new`                                 | 新增                   | users.edit + 系统管理员      |
| POST     | `/users/<uid>/delete`                        | 删除                   | users.edit + 系统管理员      |
| POST     | `/users/<uid>/password`                      | 改密（非超管仅改自己） | 登录                         |
| GET/POST | `/users/<uid>/perms`                         | 查看/保存权限          | users.view/edit + 系统管理员 |
| GET      | `/qrcodes`                                   | 二维码页               | qrcodes.view                 |
| GET      | `/qrcodes/download`                          | 下载 Word              | qrcodes.view                 |
| GET      | `/records`                                   | 出入库记录             | records.view                 |
| GET      | `/logs`                                      | 操作日志               | logs.view                    |
| GET      | `/stats`                                     | 统计页面               | stats.view                   |

### 5.2 手机端 `mobile_bp`（前缀 `/m`）

| 方法     | 路径         | 说明                     |
| :------- | :----------- | :----------------------- |
| GET/POST | `/login`     | 登录（支持 `next`）      |
| GET      | `/logout`    | 登出                     |
| GET      | `/home`      | 首页 + 物料列表          |
| GET/POST | `/inbound`   | 来料入库                 |
| GET      | `/scan`      | 无参=输入页；有参=详情页 |
| GET/POST | `/outbound`  | 领用出库（归属必填）     |
| GET/POST | `/stocktake` | 数据盘点                 |
| GET      | `/done`      | 完成页                   |

### 5.3 API `api_bp`（前缀 `/api`）

| 方法 | 路径                     | 说明                 |
| :--- | :----------------------- | :------------------- |
| GET  | `/material/<no>`         | 物料查询             |
| GET  | `/materials`             | 物料列表             |
| GET  | `/qrcode/<no>`           | 二维码图片           |
| GET  | `/stats/frequency`       | 旧版领用频率         |
| GET  | `/stats/daily_by_belong` | 折线图数据           |
| GET  | `/stats/pie_by_belong`   | 饼图数据             |
| GET  | `/stats/day_detail`      | 某天按归属分组的明细 |

------

## 6. 权限系统

### 6.1 模块定义 `utils.py`

python

```
PERM_MODULES = {
    "materials": {"view", "edit"},
    "types":     {"view", "edit"},
    "users":     {"view", "edit"},
    "qrcodes":   {"view"},
    "records":   {"view"},
    "logs":      {"view"},
    "stats":     {"view"},
}
```



### 6.2 `has_perm()`

python

```
def has_perm(module, action="view"):
    user = session.get("user")
    if not user: return False
    if user.get("username") == "admin": return True   # 超管短路
    row = db.execute(
        "SELECT can_view, can_edit FROM permissions WHERE user_id=? AND module=?",
        (user["id"], module)).fetchone()
    if not row: return False
    if action == "edit": return bool(row["can_edit"])
    return bool(row["can_view"]) or bool(row["can_edit"])
```



### 6.3 注册到 Jinja

python

```
app.jinja_env.globals["has_perm"] = has_perm
```



模板中：

jinja

```
{% if has_perm('materials', 'edit') %}
  <button>新增</button>
{% endif %}
```



### 6.4 `require_perm` 装饰器

python

```
def require_perm(module, action="view"):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_perm(module, action):
                path = request.path
                is_api = ("/api/" in path or request.is_json
                          or request.accept_mimetypes.best == "application/json")
                if is_api:
                    return jsonify(ok=False, msg="无权限"), 403
                return render_template("admin/403.html"), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco
```



### 6.5 前端控制

- 导航：`{% if has_perm('xxx','view') %}`
- 按钮：`{% if has_perm('xxx','edit') %}`
- `admin` 角色的人员管理：`{% if is_super_admin %}` 控制新增/删除/权限按钮；非超管仅显示"修改我的密码"

------

## 7. 关键实现

### 7.1 物料图片

- 上传：保存原图到 `uploads/original/`，用 Pillow 缩到 `THUMB_WIDTH=120` 存 `uploads/thumb/`
- 数据库：`image`（原图相对路径）、`image_thumb`（缩略图）
- 前端：列表 `image_thumb or image`，点击放大 `image or image_thumb`

### 7.2 导出 Excel

- 每张图片经 Pillow 读入 → 转 PNG → `XLImage(BytesIO)` 嵌入（**防止 `.mpo` / `.heic` 等扩展名触发 openpyxl 的 `KeyError`**）
- 单张失败写文字"[图片无法嵌入]"，不阻断整体

### 7.3 数据统计

- `daily_by_belong`：`GROUP BY date(created_at), belong`，补全日期序列，返回 `{labels, series:[{belong, data}]}`
- `pie_by_belong`：`GROUP BY belong`，`COUNT(*)`（次数，非数量）
- `day_detail`：按 `belong` 分组返回 `{groups:[{belong, rows_count, qty_sum, items}]}`
- 月份参数：`start_month` / `end_month`，格式 `YYYY-MM`，`monthrange()` 算月末

### 7.4 库存预警

- `warn_qty INTEGER NULL`
- 模板：`{% set warn = m.warn_qty is not none and m.warn_qty != '' and m.quantity <= m.warn_qty %}`
- CSS：`.qty-warning{ color:#ef4444; font-weight:700; }`

### 7.5 二维码

- 内容：`http://<MY_IP>:<PORT>/m/scan?materialNo=<物料号>`
- 动态生成（`/api/qrcode/<no>`），改 IP 后自动更新
- 导出 Word：`python-docx`，每行 3 个，含二维码 + 物料号 + 名称

### 7.6 后台布局

- `body.admin-body{ height:100vh; overflow:hidden }`
- `.main{ display:flex; flex-direction:column; overflow:hidden }`
- `.table-scroll{ flex:1; min-height:0; overflow:auto }`
- `thead th{ position:sticky; top:0 }`
- `table{ border-collapse:separate }`
- 隐藏滚动条：`scrollbar-width:none` + `::-webkit-scrollbar{ display:none }`

### 7.7 内网 IP

- 环境变量 `MY_IP` 优先
- UDP connect 8.8.8.8 自动探测
- 排除 `127.` / `169.254.` / `172.17+`
- 兜底 `127.0.0.1` + 启动警告
- 全局统一用 `Config.base_url()`

------

## 8. 安全要求

| 项         | 要求                                                         |
| :--------- | :----------------------------------------------------------- |
| 密码       | 当前 SHA256；建议升级为 `werkzeug.security.generate_password_hash`（加盐） |
| SECRET_KEY | 生产环境通过环境变量设置强随机值                             |
| CSRF       | 建议引入 Flask-WTF                                           |
| debug      | 生产必须 `debug=False`                                       |
| HTTPS      | 外网必须 HTTPS；内网可用自签                                 |
| 默认账号   | 首次登录后立即修改 `admin` 密码                              |
| SQL 注入   | 所有 SQL 用参数化（`?`），**禁止 f-string 拼接用户输入**     |
| XSS        | 前端 `escapeHtml()`，Jinja 默认转义                          |
| 文件上传   | 只允许 `png/jpg/jpeg/gif/webp`；`secure_filename` + uuid 重命名 |
| 权限       | 后端 `@require_perm` 强校验，前端控制仅作体验                |

------

## 9. 部署

### 9.1 环境

- Windows 10+ / Linux / macOS
- Python 3.10+
- 内存 ≥ 512 MB
- 手机与服务器同一网段

### 9.2 步骤

bash

```
mkdir trace_app && cd trace_app
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
python app.py
```



### 9.3 环境变量

bash

```
export SECRET_KEY='your-random-secret'
export MY_IP='192.168.100.133'
export PORT=5000
```



### 9.4 生产启动

bash

```
# Windows
pip install waitress
python -c "from waitress import serve; from app import create_app; serve(create_app(), host='0.0.0.0', port=5000)"

# Linux/macOS
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```



### 9.5 防火墙

bash

```
# Windows
netsh advfirewall firewall add rule name="TraceApp" dir=in action=allow protocol=TCP localport=5000

# Linux ufw
sudo ufw allow 5000/tcp
```



### 9.6 一键启动（Windows）

`start.bat`：

bat

```
@echo off
chcp 65001 >nul
title 低值易耗品管理系统
set "PROJECT_DIR=D:\trace_app"
cd /d "%PROJECT_DIR%"
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000/admin/login"
"%PROJECT_DIR%\venv\Scripts\python.exe" "%PROJECT_DIR%\app.py"
pause
```



配合 `app.py` 的 `run.lock` + PID 检测，保证**只启动一次**。

------

## 10. 测试与验收

### 10.1 功能验收清单

| #    | 场景                            | 通过标准                                                     |
| :--- | :------------------------------ | :----------------------------------------------------------- |
| 1    | `admin/admin123` 登录           | 跳物料管理                                                   |
| 2    | 新增物料（含图片、SKU、预警值） | 列表出现，缩略图正常                                         |
| 3    | 编辑物料                        | 数量不可改；SKU 多行；预警值可改                             |
| 4    | 入库 / 出库 / 盘点弹框          | 库存正确增减/覆盖，记录+日志写入                             |
| 5    | 删除物料                        | 记录保留，图片文件删除                                       |
| 6    | 导入 / 导出 Excel               | 导入覆盖/新增正确；导出含图片                                |
| 7    | 物料类别增删改                  | 正常                                                         |
| 8    | 用户新增 / 删除 / 改密          | 非 admin 角色不可删；admin 不可删                            |
| 9    | 权限弹框                        | 保存后该用户重新登录，导航与按钮按权限显示                   |
| 10   | 非系统管理员人员管理            | 只看自己，只可改自己密码                                     |
| 11   | 二维码页搜索 + 下载 Word        | 过滤正确，Word 含全部选中物料                                |
| 12   | 出入库记录三条件筛选            | 物料号 / 名称 / 归属 AND 组合                                |
| 13   | 数据统计                        | 折线图按天×归属；点击某天按归属分组明细（含备注）；饼图按次数 |
| 14   | 手机端登录 → 首页               | 两按钮 + 物料列表 + 搜索                                     |
| 15   | 扫码                            | 跳详情，图片可放大，底部两按钮                               |
| 16   | 手机入库 / 出库 / 盘点          | 归属必填；库存变化正确                                       |
| 17   | 库存预警                        | `warn_qty` 非空且库存 ≤ → 红字                               |
| 18   | 权限拦截                        | 无权限访问 URL → 403 页面；无权限 AJAX → `{ok:false}` JSON   |
| 19   | 换 IP 后二维码                  | 动态更新为新 IP                                              |
| 20   | 重复双击启动脚本                | 只启动一个进程                                               |

### 10.2 性能基线

| 指标                   | 目标  |
| :--------------------- | :---- |
| 物料 1000 条列表加载   | < 1s  |
| 统计查询（1 个月数据） | < 2s  |
| 二维码页 200 个渲染    | < 3s  |
| Excel 导出 500 条含图  | < 10s |

### 10.3 安全验收

- SQL 参数化：`grep -rn "f\"SELECT\|f'SELECT" blueprints/`，确认无用户输入拼进 SQL
- 无权限访问全部后台 URL → 403
- 上传非图片 → 拒绝
- 默认密码首次登录后可改

------

## 11. 版本记录

| 版本 | 日期       | 变更                                                         |
| :--- | :--------- | :----------------------------------------------------------- |
| v1.0 | 2025-01-01 | 初始版本：登录、物料、出入库、盘点、二维码、日志             |
| v1.1 | —          | 手机端扫码详情页；合并领用/盘点入口                          |
| v1.2 | —          | 权限系统（7 模块 view/edit）；非超管人员管理限本人           |
| v1.3 | —          | 物料 SKU 字段；详情弹框；编辑弹窗仿详情页；SKU 多行          |
| v1.4 | —          | 库存预警 `warn_qty`；列表红字                                |
| v1.5 | —          | 数据统计重构：折线图（天×归属）、饼图、点击某天按归属分组明细 |
| v1.6 | —          | 后台布局：左导航固定、查找条件 sticky、表头 sticky、隐藏滚动条 |
| v1.7 | —          | 导出 Excel 图片兼容 `.mpo` 等异常格式；一键启动防重复        |

------

## 12. 附录

### 12.1 术语

| 术语       | 说明                                                    |
| :--------- | :------------------------------------------------------ |
| 物料号     | 物料唯一标识（`material_no`）                           |
| 来料入库   | 供应商来料，库存增加                                    |
| 领用出库   | 员工领用，库存减少，归属必填                            |
| 数据盘点   | 实际清点，库存覆盖                                      |
| 归属       | 物料使用方向：方一/方二/方三/方向盘/踏板/基座/支架/其他 |
| 预警值     | 库存低于等于该值时高亮                                  |
| WAL        | SQLite 预写日志，提升并发读性能                         |
| 系统管理员 | `user_name == 'admin'` 的账号，权限恒定全开             |

### 12.2 常用命令

bash

```
# 启动
python app.py

# 生产
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"

# 备份
sqlite3 trace.db ".backup 'backup_$(date +%Y%m%d).db'"

# 检查表结构
sqlite3 trace.db "PRAGMA table_info(materials);"

# 查看日志
sqlite3 trace.db "SELECT * FROM operation_logs ORDER BY id DESC LIMIT 20;"

# 检查端口
netstat -tlnp | grep 5000
```



### 12.3 故障排查

| 现象                         | 原因                                                  | 处理                                     |
| :--------------------------- | :---------------------------------------------------- | :--------------------------------------- |
| 手机扫码跳 `/admin/login`    | `login_required` 默认跳后台                           | 按 `request.path.startswith('/m/')` 判断 |
| `Unexpected token '<'`       | 接口返回 HTML（404/403/500）                          | 看 Network 状态码，查路由/权限/异常      |
| `KeyError: '.mpo'`           | 图片扩展名异常                                        | Pillow 转 PNG 后 `XLImage(BytesIO)`      |
| `no such column: xxx`        | 数据库未迁移                                          | `ALTER TABLE ... ADD COLUMN ...`         |
| `no such table: permissions` | 建表未执行                                            | 手动建表 + `db.py` SCHEMA 补上           |
| 表头 sticky 不生效           | `border-collapse: collapse`                           | 改 `separate`                            |
| 页面卡住不滚                 | `body.admin-body{ overflow:hidden }` 但该页无滚动容器 | 加 `.table-scroll`                       |
| 重复启动两个进程             | 无锁机制                                              | `run.lock` + PID 检测                    |
| 二维码 IP 变了失效           | 静态二维码                                            | 本项目动态生成，改 IP 自动更新           |
| 导图卡死                     | 原图直嵌                                              | Pillow 缩到 160px 再嵌                   |
