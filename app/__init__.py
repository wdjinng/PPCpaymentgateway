from config import Config
from flask import Flask
from flask_cors import CORS
import sqlalchemy as db
from sqlalchemy.orm import scoped_session,sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy_session import flask_scoped_session
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask.json import JSONEncoder
from datetime import date


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, date):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)

url = '' #insert db credential here
Base = declarative_base()
engine = db.create_engine(url, echo=True, pool_size=100, max_overflow=20)
session = flask_scoped_session(sessionmaker(bind=engine))
app = Flask(__name__)
app.secret_key = "-"
app.config.from_object(Config)
cors = CORS(app)
key = app.config['SECRET_KEY']
jwt = JWTManager(app)
mail = Mail(app)
login_manager = LoginManager()
db = SQLAlchemy(app)
db.init_app(app)


from app.routers.all_router import *

app.register_blueprint(allroute_blueprint)
