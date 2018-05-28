# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import InputRequired, email, EqualTo
from wtforms import ValidationError

from ..models import User


class LoginForm(FlaskForm):
    email = StringField('邮箱', validators=[InputRequired(), email(message='邮箱格式错误')])
    password = PasswordField('密码', validators=[InputRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登录')


class RegistrationForm(FlaskForm):
    email = StringField('邮箱', validators=[InputRequired(), email(message='邮箱格式错误')])
    password = PasswordField('密码', validators=[InputRequired(), EqualTo('password_confirm', message='密码不匹配')])
    password_confirm = PasswordField('确认密码', validators=[InputRequired()])
    submit = SubmitField('注册')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('此邮箱已注册')
