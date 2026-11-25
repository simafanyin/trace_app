from flask import Flask, redirect, url_for
from config import Config
from db import init_db
from blueprints.admin import admin_bp
from blueprints.mobile import mobile_bp
from blueprints.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    init_db(app)

    # 注册模板全局函数
    from utils import has_perm, PERM_MODULES, PERM_MODULE_NAMES
    app.jinja_env.globals["has_perm"] = has_perm
    app.jinja_env.globals["PERM_MODULES"] = PERM_MODULES
    app.jinja_env.globals["PERM_MODULE_NAMES"] = PERM_MODULE_NAMES

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(mobile_bp, url_prefix="/m")
    app.register_blueprint(api_bp, url_prefix="/api")
    

    @app.route("/")
    def index():
        return redirect(url_for("admin.login"))
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=Config.PORT, debug=False)