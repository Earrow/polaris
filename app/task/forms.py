# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import InputRequired
from wtforms import ValidationError

from ..models import Task


class TaskApplyForm(FlaskForm):
    name = StringField('名称', validators=[InputRequired()])
    info = TextAreaField('说明')
    command = TextAreaField('执行命令', id='command_content')
    result_statistics = TextAreaField('结果统计', id='result_statistics_content',
                                      render_kw={'placeholder': '结果统计命令请在此配置'})
    crontab = StringField('定时设置', render_kw={'placeholder': 'crontab (minute hour day month day_of_week)'})
    scheduler_enable = BooleanField('启动定时执行')
    submit = SubmitField('提交')

    def __init__(self, project_id, **kwargs):
        super(TaskApplyForm, self).__init__(**kwargs)
        self.project_id = project_id

    def validate_name(self, field):
        if Task.query.filter_by(nickname=field.data, project_id=self.project_id).first():
            raise ValidationError('此任务已创建')


class TaskEditForm(TaskApplyForm):
    name = StringField('名称', validators=[InputRequired()], render_kw={'readonly': 'readonly'})
    submit = SubmitField('提交更改')

    def validate_name(self, field):
        pass
