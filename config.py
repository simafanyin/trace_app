import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    MY_IP = os.environ.get("MY_IP", "192.168.100.34")
    PORT = int(os.environ.get("PORT", 5000))
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trace.db")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    UPLOAD_ORIGINAL = os.path.join(UPLOAD_FOLDER, "original")  # 原图
    UPLOAD_THUMB    = os.path.join(UPLOAD_FOLDER, "thumb") # 缩略图
    THUMB_WIDTH     = 120            # 缩略图最大宽度
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 8MB