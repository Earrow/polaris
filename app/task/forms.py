# coding=utf-8

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField
from wtforms.validators import InputRequired
from wtforms import ValidationError
from flask_pagedown.fields import PageDownField

from ..models import Task


class TaskApplyForm(FlaskForm):
    name = StringField('名称', validators=[InputRequired()])
    info = TextAreaField('说明')
    command = TextAreaField('执行命令', id='command_content')
    result_statistics = TextAreaField('结果统计', id='result_statistics_content',
                                      render_kw={'placeholder': '结果统计命令请在此配置'})
    crontab = StringField('定时设置', render_kw={'placeholder': 'crontab (minute hour day month day_of_week)'})
    scheduler_enable = BooleanField('启用定时执行')
    email_receivers = StringField('通知邮件收件人地址', render_kw={'placeholder': '多个地址以;分隔'})
    email_body = PageDownField('通知邮件模板', render_kw=dict(rows=8, placeholder='模板使用Markdown格式编辑；\r\n'
                                                                            '不自定义模板则会使用默认模板；\r\n'
                                                                            '环境变量会在邮件中替换为实际内容。'))
    email_attachments = StringField('通知邮件附件', render_kw={'placeholder': '多个文件以;分隔'})
    email_notification_enable = BooleanField('启用邮件通知')
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
