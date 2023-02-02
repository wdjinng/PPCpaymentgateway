from os.path import join, dirname, realpath, abspath
import os

base_dir = abspath(dirname(__file__))

UPLOADS_PATH = join(dirname(realpath(__file__)), "app\\static\\uploads\\")


class Config(object):
    CORS_HEADERS = 'Content-Type'
    SECRET_KEY = '-'
    SECURITY_PASSWORD_SALT = str(os.environ.get("SECURITY_PASSWORD_SALT"))
    JSON_SORT_KEYS = False
    JWT_SECRET_KEY = str(os.environ.get("JWT_SECRET"))
    UPLOAD_FOLDER = UPLOADS_PATH
    MAIL_SERVER = '-'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = '-'  # enter your email here
    MAIL_DEFAULT_SENDER = '-'  # enter your email here
    MAIL_PASSWORD = '-'  # enter your password here
