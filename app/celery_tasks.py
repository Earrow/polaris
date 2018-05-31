# coding=utf-8

import redis
from flask import current_app
from flask_login import current_user

from . import db, jenkins, celery_app
from .tools import gen_analysis_pic
from .models import Record, Project, Task, Result, EmailTemplate

r = redis.Redis('localhost')


@celery_app.task(name='app.celery_tasks.send_email')
def send_email(host, sender, pwd, receivers, subject, content, result=None, attachments=None, content_type='html'):
    """发送邮件。

    :param host: 邮件发送服务器
    :type host: str
    :param sender: 邮件发送账号
    :type sender: str
    :param pwd: 邮件发送账号的密码
    :type pwd: str
    :param receivers: 邮件接收地址
    :type receivers: list
    :param subject: 邮件主题
    :type subject: str
    :param content: 邮件正文
    :type content: str
    :param result: 测试结果数据，由测试用例数、出错数、失败数、跳过数组成的元组
    :type result: tuple
    :param attachments: 附件，传入各附件组成的列表，每个附件为附件名、附件二进制内容组成的元组
    :type attachments: list
    :param content_type: 邮件正文格式，可传入'html'、'plain'等，默认'html'
    :type content_type: str
    """
    import smtplib
    from email import encoders
    from email.header import Header
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receivers)
    msg['Subject'] = Header(subject, 'utf-8')

    if result:
        result_pic = gen_analysis_pic(result[2], result[0] - result[1] - result[2] - result[3], result[3], result[1])
        att = MIMEBase('image', 'png', filename='analysis.png')
        att.add_header('Content-Disposition', 'attachment', filename='analysis.png')
        att.add_header('Content-ID', '<0>')
        att.add_header('X-Attachment-Id', '0')
        att.set_payload(result_pic)
        encoders.encode_base64(att)
        msg.attach(att)

        content = content.replace('${analysis_pic}', '<img src="cid:0" />')

    # 正文
    msg.attach(MIMEText(content, content_type, 'utf-8'))

    if attachments:
        for attachment_name, attachment_content in attachments:
            att = MIMEText(attachment_content, 'base64', 'utf-8')
            att["Content-Type"] = 'application/octet-stream'
            att["Content-Disposition"] = f'attachment; filename="{attachment_name}"'
            msg.attach(att)

    smtp = smtplib.SMTP_SSL(host)
    smtp.login(sender, pwd)
    smtp.sendmail(sender, receivers, msg.as_string())
    smtp.quit()


@celery_app.task(name='app.celery_tasks.check_state')
def check_state():
    """检查所有任务的执行状态。"""

    projects = Project.query.all()
    for p in projects:
        tasks = Task.query.filter_by(project=p).all()
        for task in tasks:
            job_info = jenkins._server.get_job_info(task.name)
            builds = job_info['builds'][::-1]
            for build in builds:
                build_number = build['number']

                # 根据jenkins的构建记录查询数据库中的记录
                rcd = Record.query.filter_by(task=task).filter_by(build_number=build_number).first()

                # 数据库中没有该记录，则添加进去
                if rcd is None:
                    rcd = Record(user=None, project=p, task=task, state=0, version='9999',
                                 build_number=build_number)
                    db.session.add(rcd)
                    db.session.commit()

                if rcd.state == -2:
                    try:
                        rcd.state = 0
                        db.session.commit()
                    except jenkins.NotFoundException:
                        pass

                # 查询记录是否已经执行完毕
                if rcd.state == 0:
                    build_info = jenkins._server.get_build_info(rcd.task.name, rcd.build_number)
                    if build_info['result']:
                        console_output = jenkins._server.get_build_console_output(rcd.task.name, rcd.build_number)

                        test_result = Result(record=rcd, status=0 if build_info['result'] == 'SUCCESS' else -1,
                                             cmd_line=console_output, tests=0, errors=0, failures=0, skip=0)

                        tests = f'result:tests:{rcd.project.name}:{rcd.task.nickname}'
                        errors = f'result:errors:{rcd.project.name}:{rcd.task.nickname}'
                        failures = f'result:failures:{rcd.project.name}:{rcd.task.nickname}'
                        skip = f'result:skip:{rcd.project.name}:{rcd.task.nickname}'

                        if r.exists(tests):
                            test_result.tests += int(r.get(tests))
                            test_result.errors += int(r.get(errors))
                            test_result.failures += int(r.get(failures))
                            test_result.skip += int(r.get(skip))

                            r.delete(tests, errors, failures, skip)

                        db.session.add(test_result)

                        if build_info['result'] == 'SUCCESS':
                            rcd.state = 1
                        else:
                            rcd.state = -1
                        rcd.result = test_result
                        db.session.commit()

                        if rcd.task.email_notification_enable and rcd.task.email_receivers:
                            receivers = rcd.task.email_receivers.replace('， ', ',').replace(', ', ',').replace('，', ',')
                            receivers = receivers.split(',')
                            send_email.delay(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_SENDER'],
                                             current_app.config['EMAIL_SENDER_PASSWORD'],
                                             receivers, f'{rcd.task.name} 测试结果：{"成功" if rcd.state == 1 else "失败"}',
                                             EmailTemplate.query.order_by(
                                                 EmailTemplate.timestamp.desc()).first().body_html,
                                             (test_result.tests, test_result.errors, test_result.failures,
                                              test_result.skip) if test_result.tests != 0 else None,
                                             [('console.log',
                                               test_result.cmd_line.replace('\n', '\r\n').encode('utf8'))])
