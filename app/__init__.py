from flask import Flask, request, has_request_context
from flask_babel import Babel, _
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from config import Config

db=SQLAlchemy()
login_manager=LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/json/*": {"origins":"*"}})
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view='register'
    def get_locale() :
        if has_request_context() :
            lang = request.cookies.get('lang','en')
        else :
            lang = 'en'
        if lang in app.config['BABEL_SUPPORTED_LOCALES']:
            return lang
        return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
    babel = Babel(app, locale_selector=get_locale)
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    app.jinja_env.globals.update(get_locale=get_locale)
    with app.app_context() :
        from app import routes
    return app





