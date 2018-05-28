# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import InputRequired, IPAddress
from wtforms import ValidationError

from ..models import Server


class ServerCreateForm(FlaskForm):
    host = StringField('IP地址', validators=[InputRequired(), IPAddress(message='IP格式错误')])
    username = StringField('用户名', validators=[InputRequired()])
    password = StringField('密码', validators=[InputRequired()])
    workspace = StringField('工作目录', validators=[InputRequired()])
    info = TextAreaField('描述')
    submit = SubmitField('提交')

    def validate_host(self, field):
        if Server.query.filter_by(host=field.data).first():
            raise ValidationError('此服务器已添加')


class ServerEditForm(ServerCreateForm):
    host = StringField('IP地址', validators=[InputRequired(), IPAddress(message='IP格式错误')],
                       render_kw={'readonly': 'readonly'})
    submit = SubmitField('提交更改')

    def validate_host(self, field):
        pass
