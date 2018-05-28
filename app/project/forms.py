# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import InputRequired
from wtforms import ValidationError

from ..models import Project, Server


class ProjectApplyForm(FlaskForm):
    def __init__(self, **kwargs):
        super(ProjectApplyForm, self).__init__(**kwargs)

        self.server_id.choices = [(server.id, server.host) for server in Server.query.all()]

    name = StringField('名称', validators=[InputRequired()])
    info = TextAreaField('说明')
    server_id = SelectField('测试服务器', coerce=int)
    submit = SubmitField('提交')

    def validate_name(self, field):
        if Project.query.filter_by(name=field.data).first():
            raise ValidationError('此项目已创建')


class ProjectEditForm(ProjectApplyForm):
    name = StringField('名称', validators=[InputRequired()], render_kw={'readonly': 'readonly'})
    submit = SubmitField('提交更改')

    def validate_name(self, field):
        pass
