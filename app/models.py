# coding=utf-8

import logging

from datetime import datetime

from flask import current_app
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from markdown import markdown
import bleach

from . import db, login_manager

logger = logging.getLogger('polaris.models')


class Permission:
    TEST = 0x01  # 执行测试
    ADMINISTER = 0x80  # 平台管理


class Role(db.Model):
    """用户角色。"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    users = db.relationship('User', backref='role', lazy='dynamic')
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)

    @staticmethod
    def insert_roles():
        roles = {
            'Tester': (Permission.TEST, True),
            'Administrator': (Permission.TEST | Permission.ADMINISTER, False)
        }

        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if not role:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role {}>'.format(self.name)


# 用户和项目的注册关系
testable_registrations = db.Table('testable_registrations',
                                  db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                                  db.Column('project_id', db.Integer, db.ForeignKey('projects.id')))
editable_registrations = db.Table('editable_registrations',
                                  db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
                                  db.Column('project_id', db.Integer, db.ForeignKey('projects.id')))


class RegistrationApplication(db.Model):
    """用户加入项目申请。"""
    __tablename__ = 'registration_applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    state = db.Column(db.Integer, default=0)  # 0：未处理，1：批准或用户被直接添加到项目，-1：拒绝
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


class ProjectApplication(db.Model):
    """项目申请。"""
    __tablename__ = 'project_applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    state = db.Column(db.Integer, default=0)  # 0：未处理，1：批准，-1：拒绝
    showed = db.Column(db.Boolean, default=False)  # 申请被拒绝后在用户第一次访问项目列表时会显示拒绝信息
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


class User(UserMixin, db.Model):
    """用户。"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    active_project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    records = db.relationship('Record', backref='user', lazy='dynamic')
    testable_projects = db.relationship('Project', secondary=testable_registrations,
                                        backref=db.backref('testers', lazy='dynamic'), lazy='dynamic')
    editable_projects = db.relationship('Project', secondary=editable_registrations,
                                        backref=db.backref('editors', lazy='dynamic'), lazy='dynamic')
    registration_applications = db.relationship('RegistrationApplication', backref='user', lazy='dynamic')
    project_applications = db.relationship('ProjectApplication', backref='user', lazy='dynamic')
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)

        # 为用户增加权限，若用户账号在系统管理员配置中，则添加管理员角色；否则添加默认角色
        if self.role is None:
            if self.email == current_app.config['POLARIS_ADMIN']:
                self.role = Role.query.filter_by(name='Administrator').first()
            else:
                self.role = Role.query.filter_by(default=True).first()
            logger.debug('create user {}, role as {}'.format(self, self.role))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can(self, permissions):
        """校验用户是否具有某个权限。

        :param permissions: 权限值（Permission类变量）
        :type permissions: int
        :return: True if user has permissions else False
        """
        return self.role.permissions & permissions == permissions

    def is_administrator(self):
        """校验用户是否是管理员。

        :return: True if user is administrator else False
        """
        return self.can(Permission.ADMINISTER)

    def register(self, project, editable=False):
        """注册用户到项目。

        :param project: 项目。
        :type project: Project
        :param editable: 是否将用户注册为项目管理员。
        :type editable: boolean
        :return: None
        """
        if editable:
            self.editable_projects.append(project)
            project.editors.append(self)
        else:
            self.testable_projects.append(project)
            project.testers.append(self)

        if not self.active_project:
            self.active_project = project

        db.session.add(self)
        db.session.add(project)
        db.session.commit()

    def __repr__(self):
        return '<User {}>'.format(self.email)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser


class Server(db.Model):
    """测试服务器。"""
    __tablename__ = 'servers'

    id = db.Column(db.Integer, primary_key=True)
    projects = db.relationship('Project', backref='server', lazy='dynamic')
    host = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64))
    password = db.Column(db.String(64))
    workspace = db.Column(db.String(64))
    info = db.Column(db.Text)

    def __repr__(self):
        return '<Server {}>'.format(self.host)


class Project(db.Model):
    """项目。"""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'))
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    active_users = db.relationship('User', backref='active_project', lazy='dynamic')
    registration_applications = db.relationship('RegistrationApplication', backref='project', lazy='dynamic')
    project_applications = db.relationship('ProjectApplication', backref='project', lazy='dynamic')
    records = db.relationship('Record', backref='project', lazy='dynamic')
    name = db.Column(db.String(64), unique=True, index=True)
    info = db.Column(db.Text)
    allowed = db.Column(db.Boolean, default=False)  # 是否已经被批准创建

    @staticmethod
    def on_created(target, value, old_value, initiator):
        """添加新项目时，将其与平台管理员关联起来"""
        for u in User.query.all():
            if u.is_administrator():
                logger.debug('create project {}, auto register the user {} to it'.format(value, u))
                u.register(target, True)

    def __repr__(self):
        return '<Project {}>'.format(self.name)


db.event.listen(Project.name, 'set', Project.on_created)


class Task(db.Model):
    """测试任务。"""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    records = db.relationship('Record', backref='task', lazy='dynamic')
    nickname = db.Column(db.String(64), index=True)
    name = db.Column(db.String(64), index=True)  # 全名，项目名_nickname
    info = db.Column(db.Text)
    command = db.Column(db.Text)
    result_statistics = db.Column(db.Text)
    crontab = db.Column(db.String(64))
    scheduler_enable = db.Column(db.Boolean, default=False)
    email_receivers = db.Column(db.Text)
    email_notification_enable = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<Task {}>'.format(self.name)


class Record(db.Model):
    """测试任务执行记录。"""
    __tablename__ = 'records'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    result = db.relationship('Result', backref='record', uselist=False)
    build_number = db.Column(db.Integer)  # jenkins的build number
    version = db.Column(db.String(64))
    state = db.Column(db.Integer, default=-2)  # -1：执行失败，0：执行中，1：执行成功，-2：等待执行
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return '<Record of {}-{}-version {}>'.format(self.project, self.task, self.version)


class Result(db.Model):
    """测试任务执行结果。"""
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('records.id'))
    cmd_line = db.Column(db.Text)  # 命令行输出
    status = db.Column(db.Integer)  # 任务退出码，0：成功，-1：失败
    tests = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    failures = db.Column(db.Integer, default=0)
    skip = db.Column(db.Integer, default=0)


class Manual(db.Model):
    """使用说明。"""
    __tablename__ = 'manuals'

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    @staticmethod
    def insert_manual():
        import os
        with open(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'static', 'manual.txt'),
                  encoding='utf-8') as fp:
            data = fp.read()
            m = Manual(body=data)
            db.session.add(m)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        target.body_html = bleach.linkify(markdown(value, output_format='html'))


db.event.listen(Manual.body, 'set', Manual.on_changed_body)


class EmailTemplate(db.Model):
    """邮件通知模板。"""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    @staticmethod
    def insert_email_template():
        import os
        with open(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'static', 'email_template.txt'),
                  encoding='utf-8') as fp:
            data = fp.read()
            m = EmailTemplate(body=data)
            db.session.add(m)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        target.body_html = bleach.linkify(markdown(value, output_format='html'))


db.event.listen(EmailTemplate.body, 'set', EmailTemplate.on_changed_body)
