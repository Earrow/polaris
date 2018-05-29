# coding=utf-8

import logging

from flask_jenkins import Jenkins
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_apscheduler import APScheduler
from flask_pagedown import PageDown

from config import config

logger = logging.getLogger('polaris.app')

login_manager = LoginManager()
login_manager.session_protection = 'basic'
login_manager.login_view = 'auth.login'
login_manager.login_message = '请登录以访问该页面'
login_manager.login_message_category = 'warning'

db = SQLAlchemy()
bootstrap = Bootstrap()
scheduler = APScheduler()
jenkins = Jenkins()
pagedown = PageDown()


def create_app(config_name):
    app = Flask(__name__)
    logger.debug('create app, using config: {}'.format(config_name))
    logger.debug('config content: {}'.format(config[config_name]))
    app.config.from_object(config[config_name])

    login_manager.init_app(app)
    db.init_app(app)
    bootstrap.init_app(app)
    scheduler.init_app(app)
    jenkins.init_app(app)
    pagedown.init_app(app)

    from .project import project as project_blueprint
    from .auth import auth as auth_blueprint
    from .admin import admin as admin_blueprint
    from .task import task as task_blueprint
    from .record import record as record_blueprint
    from .server import server as server_blueprint
    from .main import main as main_blueprint
    from .user import user as user_blueprint

    app.register_blueprint(main_blueprint)
    app.register_blueprint(project_blueprint, url_prefix='/projects')
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(task_blueprint, url_prefix='/tasks')
    app.register_blueprint(record_blueprint, url_prefix='/records')
    app.register_blueprint(server_blueprint, url_prefix='/servers')
    app.register_blueprint(user_blueprint, url_prefix='/users')

    return app
