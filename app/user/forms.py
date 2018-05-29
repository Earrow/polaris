# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, RadioField, SubmitField
from wtforms.validators import InputRequired


class AddUserForm(FlaskForm):
    new_user_email = StringField('用户邮箱地址', validators=[InputRequired()])
    new_user_permission = RadioField('权限', choices=[('editor', '管理员'), ('tester', '测试员')])
    submit = SubmitField('添加')
