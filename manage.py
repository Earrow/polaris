# coding=utf-8

from app import db, app
from app.models import User, Role, Task, Result, Project, Record, Manual, EmailTemplate, OperatingRecord
from flask_script import Manager, Shell, Server
from flask_migrate import MigrateCommand

manager = Manager(app)


def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role, Task=Task, Result=Result, Project=Project, Record=Record,
                Manual=Manual, EmailTemplate=EmailTemplate, OperatingRecord=OperatingRecord)


manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('runserver', Server(host='0.0.0.0'))
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
