# coding=utf-8

import json

import redis
from flask import render_template, url_for, request, jsonify, current_app, abort
from flask_login import current_user, login_required

from . import record
from .. import db, jenkins
from ..celery_tasks import send_email
from ..models import Record, Project, Task, Result, EmailTemplate

r = redis.Redis('localhost')


@record.route('/')
@login_required
def record_list():
    project_id = request.args.get('project_id', type=int)
    task_id = request.args.get('task_id', type=int)
    page = request.args.get('page', 1, type=int)

    p = Project.query.get(project_id)
    if current_user not in p.testers and current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is disallowed to get record list of project {project_id} '
                                   f'task {task_id}')
        abort(403)

    current_app.logger.debug('get {}'.format(url_for('.record_list', project_id=project_id, task_id=task_id,
                                                     page=page)))

    if task_id != -1:
        pagination = Record.query.filter_by(project_id=project_id, task_id=task_id).order_by(
            Record.timestamp.desc()).paginate(page, per_page=current_app.config['POLARIS_RECORDS_PER_PAGE'],
                                              error_out=False)
    else:
        pagination = Record.query.filter_by(project_id=project_id).order_by(
            Record.timestamp.desc()).paginate(page, per_page=current_app.config['POLARIS_RECORDS_PER_PAGE'],
                                              error_out=False)

    test_records = pagination.items
    current_app.logger.debug(f'get records: {test_records}')
    return render_template('record/records.html', records=test_records, pagination=pagination, project_id=project_id,
                           task_id=task_id)


@record.route('/<record_id>/console/')
@login_required
def console(record_id):
    test_record = Record.query.get(record_id)
    p = test_record.project

    if current_user not in p.testers and current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is disallowed to get console output of record {test_record}')
        abort(403)

    current_app.logger.debug('get {}'.format(url_for('.console', record_id=record_id)))

    console_output = jenkins._server.get_build_console_output(test_record.task.name, test_record.build_number).replace(
        '\r', '').replace('\n', '<br>')
    r.set('console_output:{}:{}'.format(test_record.task.name, test_record.build_number), console_output)

    return render_template('record/console.html', ret=console_output, task_name=test_record.task.name,
                           build_number=test_record.build_number)


@record.route('/console_check/')
def console_check():
    task_name = request.args.get('task_name')
    build_number = request.args.get('build_number', type=int)
    current_app.logger.debug('get {}'.format(url_for('.console_check', task_name=task_name, build_number=build_number)))

    console_output_cache = r.get('console_output:{}:{}'.format(task_name, build_number)).decode('utf-8')
    console_output = jenkins._server.get_build_console_output(task_name, build_number).replace('\r', '').replace('\n',
                                                                                                                 '<br>')
    r.set('console_output:{}:{}'.format(task_name, build_number), console_output)

    build_info = jenkins._server.get_build_info(task_name, build_number)
    if build_info['result']:
        end = True
        current_app.logger.info('build end')
    else:
        end = False

    return jsonify(ret=console_output.lstrip(console_output_cache), end=end)


@record.route('/<record_id>/analysis/')
@login_required
def analysis(record_id):
    """单次执行记录结果统计。"""
    test_record = Record.query.get(record_id)
    p = test_record.project

    if current_user not in p.testers and current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is disallowed to get analysis of record {test_record}')
        abort(403)

    current_app.logger.debug('get {}'.format(url_for('.analysis', record_id=record_id)))

    if test_record.result:
        if test_record.result.tests:
            ret = {
                'tests': test_record.result.tests,
                'errors': test_record.result.errors,
                'failures': test_record.result.failures,
                'skip': test_record.result.skip
            }
        else:
            current_app.logger.debug('test result not report')
            ret = '测试结果未上报'
    else:
        current_app.logger.debug('test not end')
        ret = '请等待测试结束后再查看'

    return render_template('record/analysis.html', ret=ret)


@record.route('/report_result', methods=['POST'])
def report_result():
    """接收测试结果数据上报。"""
    result = json.loads(request.get_data().decode('utf-8'))
    current_app.logger.info(f'get result report: {result}')

    r.rpush(f'result:tests:{result["project_name"]}:{result["task_name"]}', result['tests'])
    r.rpush(f'result:errors:{result["project_name"]}:{result["task_name"]}', result['errors'])
    r.rpush(f'result:failures:{result["project_name"]}:{result["task_name"]}', result['failures'])
    r.rpush(f'result:skip:{result["project_name"]}:{result["task_name"]}', result['skip'])

    return jsonify(status=0, msg='ok')


@record.route('/check_state/')
def check_state():
    """检查某个任务执行状态，通过ajax调用。"""
    task_id = request.args.get('task_id', type=int)
    task = Task.query.get(task_id)
    current_app.logger.debug('get {}'.format(url_for('.check_state', task_id=task_id)))

    state = 0  # 是否有测试任务已经执行结束，0：没有，1：有。若有结束的任务，则测试记录页面需要自动刷新

    if task:
        job_info = jenkins._server.get_job_info(task.name)
        current_app.logger.debug(f'job info: {job_info}')

        build = job_info['builds'][0]
        build_number = build['number']

        # 根据jenkins的构建记录查询数据库中的记录
        rcd = Record.query.filter_by(task=task).filter_by(build_number=build_number).first()
        current_app.logger.debug(f'record of the task: {rcd}')

        if rcd.state == -2:
            rcd.state = 0
            db.session.commit()

        # 查询记录是否已经执行完毕
        if rcd.state == 0:
            build_info = jenkins._server.get_build_info(rcd.task.name, rcd.build_number)
            if build_info['result']:
                console_output = jenkins._server.get_build_console_output(rcd.task.name, rcd.build_number)

                test_result = Result(record=rcd, status=0 if build_info['result'] == 'SUCCESS' else -1,
                                     cmd_line=console_output, tests=0, errors=0, failures=0, skip=0)

                tests = r.lpop(f'result:tests:{rcd.project.name}:{rcd.task.nickname}')
                errors = r.lpop(f'result:errors:{rcd.project.name}:{rcd.task.nickname}')
                failures = r.lpop(f'result:failures:{rcd.project.name}:{rcd.task.nickname}')
                skip = r.lpop(f'result:skip:{rcd.project.name}:{rcd.task.nickname}')

                if tests:
                    test_result.tests += int(tests)
                    test_result.errors += int(errors)
                    test_result.failures += int(failures)
                    test_result.skip += int(skip)

                db.session.add(test_result)

                if build_info['result'] == 'SUCCESS':
                    current_app.logger.debug('{} success'.format(rcd))
                    rcd.state = 1
                else:
                    current_app.logger.debug('{} fail'.format(rcd))
                    rcd.state = -1
                rcd.result = test_result
                db.session.commit()

                state = 1

                if rcd.task.email_notification_enable and rcd.task.email_receivers:
                    receivers = rcd.task.email_receivers.replace('， ', ',').replace(', ', ',').replace('，', ',')
                    receivers = receivers.split(',')
                    send_email.delay(current_app.config['EMAIL_HOST'], current_app.config['EMAIL_SENDER'],
                                     current_app.config['EMAIL_SENDER_PASSWORD'],
                                     receivers, f'{rcd.task.name} 测试结果：{"成功" if rcd.state == 1 else "失败"}',
                                     EmailTemplate.query.order_by(EmailTemplate.timestamp.desc()).first().body_html,
                                     (test_result.tests, test_result.errors, test_result.failures, test_result.skip) if
                                     test_result.tests != 0 else None,
                                     [('console.log', test_result.cmd_line.replace('\n', '\r\n').encode('utf8'))])

    return jsonify(state=state)


@record.route('/do_test')
@login_required
def do_test():
    """执行测试接口，通过ajax调用。"""
    project_id = request.args.get('project_id', type=int)
    task_id = request.args.get('task_id', type=int)
    version = request.args.get('version')
    current_app.logger.debug(f'get {url_for(".do_test", project_id=project_id, task_id=task_id, version=version)}')

    p = Project.query.get(project_id)
    t = Task.query.get(task_id)

    if current_user not in p.testers and current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is disallowed to do test of task {t}')
        return jsonify(state='no_permission')

    build_number = jenkins._server.get_job_info(t.name)['nextBuildNumber']
    current_app.logger.debug(f'build number: {build_number}')

    if not jenkins._server.get_node_info(p.server.host)['offline']:
        # 测试服务器在线
        if Record.query.filter_by(task=t, state=0).first() or Record.query.filter_by(task=t, state=-2).first():
            # 该任务正在执行中
            current_app.logger.debug('the task is in testing')
            return jsonify(state='busy')

        test_record = Record(user=current_user, project=p, task=t, state=0, version=version, build_number=build_number)
        db.session.add(test_record)
        db.session.commit()
        jenkins._server.build_job(t.name)

        current_app.logger.info(f'created record: {test_record}')
        return jsonify(state='success')
    else:
        # 测试服务器离线
        current_app.logger.warning(f'{p.server} offline')

        if not Record.query.filter_by(task=t, state=-2).first():
            test_record = Record(user=current_user, project=p, task=t, state=-2, version=version,
                                 build_number=build_number)
            db.session.add(test_record)
            db.session.commit()

            current_app.logger.info(f'created record: {test_record}')
            return jsonify(state='timeout')
        else:
            return jsonify(state='wait')
