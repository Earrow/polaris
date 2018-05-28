# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import InputRequired
from flask_pagedown.fields import PageDownField


class ManualForm(FlaskForm):
    body = PageDownField('内容：', validators=[InputRequired()], render_kw=dict(rows=15))
    submit = SubmitField('提交')
