# encoding=utf-8

from apscheduler.triggers.cron import CronTrigger
from flask import render_template, url_for, redirect, abort, flash, current_app, request
from flask_login import current_user, login_required
from jenkins import JenkinsException

from . import task
from .. import db, scheduler, jenkins
from .forms import TaskApplyForm, TaskEditForm
from ..models import Project, Task, Record


def _create_job(name, info, command, result_statistics, host):
    """向jenkins添加任务。"""
    import xml.etree.ElementTree as ET

    project = ET.Element('project')

    project.append(ET.Element('actions'))

    description = ET.Element('description')
    description.text = info.replace('\r', '')
    project.append(description)

    keepDependencies = ET.Element('keepDependencies')
    keepDependencies.text = 'false'
    project.append(keepDependencies)

    project.append(ET.Element('properties'))

    project.append(ET.Element('scm', {'class': 'hudson.scm.NullSCM'}))

    assignedNode = ET.Element('assignedNode')
    assignedNode.text = host
    project.append(assignedNode)

    canRoam = ET.Element('canRoam')
    canRoam.text = 'false'
    project.append(canRoam)

    disabled = ET.Element('disabled')
    disabled.text = 'false'
    project.append(disabled)

    blockBuildWhenDownstreamBuilding = ET.Element('blockBuildWhenDownstreamBuilding')
    blockBuildWhenDownstreamBuilding.text = 'false'
    project.append(blockBuildWhenDownstreamBuilding)

    blockBuildWhenUpstreamBuilding = ET.Element('blockBuildWhenUpstreamBuilding')
    blockBuildWhenUpstreamBuilding.text = 'false'
    project.append(blockBuildWhenUpstreamBuilding)

    project.append(ET.Element('triggers'))

    concurrentBuild = ET.Element('concurrentBuild')
    concurrentBuild.text = 'false'
    project.append(concurrentBuild)

    builders = ET.Element('builders')
    ET.SubElement(ET.SubElement(builders, 'hudson.tasks.Shell'), 'command').text = command.replace('\r', '')
    project.append(builders)

    publishers = ET.Element('publishers')
    # 结果统计
    post_build_script = ET.Element('org.jenkinsci.plugins.postbuildscript.PostBuildScript',
                                   {'plugin': 'postbuildscript@2.7.0'})
    config = ET.Element('config')
    build_steps = ET.Element('buildSteps')
    build_step = ET.Element('org.jenkinsci.plugins.postbuildscript.model.PostBuildStep')
    results = ET.Element('results')
    result_success = ET.Element('string')
    result_success.text = 'SUCCESS'
    result_failure = ET.Element('string')
    result_failure.text = 'FAILURE'
    role = ET.Element('role')
    role.text = 'BOTH'
    build_steps_sub = ET.Element('buildSteps')
    shell = ET.Element('hudson.tasks.Shell')
    command = ET.Element('command')
    command.text = result_statistics.replace('\r', '')
    mark_build_unstable = ET.Element('markBuildUnstable')
    mark_build_unstable.text = 'false'

    shell.append(command)
    build_steps_sub.append(shell)
    results.append(result_failure)
    results.append(result_success)
    build_step.append(results)
    build_step.append(role)
    build_step.append(build_steps_sub)
    build_steps.append(build_step)
    config.append(ET.Element('scriptFiles'))
    config.append(ET.Element('groovyScripts'))
    config.append(build_steps)
    config.append(mark_build_unstable)
    post_build_script.append(config)
    publishers.append(post_build_script)

    project.append(publishers)

    project.append(ET.Element('buildWrappers'))

    config = ET.tostring(project).decode('utf-8')
    jenkins._server.create_job(name, config)

    return config


@task.route('/')
def task_list():
    project_id = request.args.get('project_id', type=int)
    page = request.args.get('page', 1, type=int)
    current_app.logger.debug('get {}'.format(url_for('.task_list', project_id=project_id, page=page)))

    pagination = Task.query.filter_by(project_id=project_id).paginate(page, per_page=current_app.config[
        'POLARIS_TASKS_PER_PAGE'], error_out=False)
    t = pagination.items
    p = Project.query.get(project_id)
    return render_template('task/tasks.html', pagination=pagination, tasks=t, project=p)


@task.route('/<task_id>/', methods=['GET', 'POST'])
@login_required
def task_info(task_id):
    """编辑任务。"""
    t = Task.query.get(task_id)
    form = TaskEditForm(t.project.id)
    p = Project.query.get(t.project.id)

    if form.validate_on_submit():
        if current_user not in p.editors:
            current_app.logger.warning(f'user {current_user} is forbade to edit the task {t}')
            abort(403)

        current_app.logger.debug('post {}'.format(url_for('.task_info', task_id=task_id)))

        try:
            import xml.etree.ElementTree as ET

            config = jenkins._server.get_job_config(t.name)
            root = ET.fromstring(config)

            if form.info.data != t.info:
                current_app.logger.debug('info updated')

                root.find('description').text = form.info.data

            if form.command.data != t.command:
                current_app.logger.debug('command updated')

                root.find('builders').find('hudson.tasks.Shell').find('command').text = form.command.data.replace('\r',
                                                                                                                  '')
            if form.result_statistics.data != t.result_statistics:
                current_app.logger.debug('result_statistics updated')

                root.find('.//org.jenkinsci.plugins.postbuildscript.model.PostBuildStep//command').text = \
                    form.result_statistics.data.replace('\r', '')

            jenkins._server.reconfig_job(t.name, ET.tostring(root).decode('utf-8'))

            t.nickname = form.name.data
            t.info = form.info.data
            t.command = form.command.data
            t.result_statistics = form.result_statistics.data
            t.email_receivers = form.email_receivers.data
            t.email_body = form.email_body.data
            t.email_attachments = form.email_attachments.data
            t.email_notification_enable = form.email_notification_enable.data

            db.session.commit()

            if form.scheduler_enable.data:
                if form.crontab.data:
                    current_app.logger.debug('edit trigger of <Task {}>'.format(form.name.data))

                    # 校验crontab格式
                    scheduler.add_job('temp_id', lambda: None, trigger=CronTrigger.from_crontab(form.crontab.data))
                    scheduler.remove_job('temp_id')

                    triggers = root.find('triggers')
                    timer_trigger = triggers.find('hudson.triggers.TimerTrigger')
                    if timer_trigger:
                        timer_trigger.find('spec').text = form.crontab.data
                    else:
                        timer_trigger = ET.SubElement(triggers, 'hudson.triggers.TimerTrigger')
                        spec = ET.SubElement(timer_trigger, 'spec')
                        spec.text = form.crontab.data

                    jenkins._server.reconfig_job(t.name, ET.tostring(root).decode('utf-8'))
                    # 防止jenkins出错，对定时的设置单独修改
                    t.crontab = form.crontab.data
                    t.scheduler_enable = form.scheduler_enable.data
                else:
                    flash('未配置crontab', 'warning')
                    t.scheduler_enable = False
            else:
                triggers = root.find('triggers')
                timer_trigger = triggers.find('hudson.triggers.TimerTrigger')
                if timer_trigger:
                    triggers.remove(timer_trigger)
                    jenkins._server.reconfig_job(t.name, ET.tostring(root).decode('utf-8'))

                t.crontab = form.crontab.data
                t.scheduler_enable = form.scheduler_enable.data

            current_app.logger.info(f'{current_user} edited {t}')
            db.session.commit()
        except ValueError as e:
            t.scheduler_enable = False
            db.session.commit()

            current_app.logger.error('crontab wrong')
            current_app.logger.exception(e)
            flash('crontab格式错误', 'danger')
        except JenkinsException as e:
            current_app.logger.error('jenkins edit job error')
            current_app.logger.exception(e)
            flash('内部错误', 'danger')

        return redirect(url_for('.task_list', project_id=t.project.id))

    current_app.logger.debug('get {}'.format(url_for('.task_info', project_id=t.project.id, task_id=task_id)))

    form.name.data = t.nickname
    form.info.data = t.info
    form.command.data = t.command
    form.result_statistics.data = t.result_statistics
    form.crontab.data = t.crontab
    form.scheduler_enable.data = t.scheduler_enable
    form.email_receivers.data = t.email_receivers
    form.email_body.data = t.email_body
    form.email_attachments.data = t.email_attachments
    form.email_notification_enable.data = t.email_notification_enable

    if current_user in p.editors:
        return render_template('task/task.html', form=form, can_edit=True)
    else:
        return render_template('task/task.html', form=form, can_edit=False)


@task.route('/create/', methods=['GET', 'POST'])
def create():
    """创建新任务。"""
    project_id = request.args.get('project_id', type=int)

    p = Project.query.get(project_id)
    form = TaskApplyForm(project_id)

    if current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is forbade to create task')
        abort(403)

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.create', project_id=project_id)))

        task_name = f'{p.name}_{form.name.data}'

        try:
            jenkins._server.delete_job(task_name)
            current_app.logger.warning(f'{task_name} already exist in jenkins, delete it')
        except JenkinsException:
            pass

        try:
            _create_job(task_name, form.info.data, form.command.data, form.result_statistics.data, p.server.host)

            t = Task(name=task_name, nickname=form.name.data, info=form.info.data, command=form.command.data,
                     result_statistics=form.result_statistics.data, crontab=form.crontab.data,
                     scheduler_enable=form.scheduler_enable.data, email_receivers=form.email_receivers.data,
                     email_body=form.email_body.data, email_attachments=form.email_attachments.data,
                     email_notification_enable=form.email_notification_enable.data, project=p)
            db.session.add(t)
            db.session.commit()
            current_app.logger.info('{} created the task {}'.format(current_user, t))

            if form.scheduler_enable.data:
                if form.crontab.data:
                    current_app.logger.debug('add trigger to <Task {}>'.format(t.name))

                    import xml.etree.ElementTree as ET

                    config = jenkins._server.get_job_config(t.name)
                    root = ET.fromstring(config)

                    # 校验crontab格式
                    scheduler.add_job('temp_id', lambda: None, trigger=CronTrigger.from_crontab(form.crontab.data))
                    scheduler.remove_job('temp_id')

                    triggers = root.find('triggers')
                    timer_trigger = ET.SubElement(triggers, 'hudson.triggers.TimerTrigger')
                    spec = ET.SubElement(timer_trigger, 'spec')
                    spec.text = form.crontab.data

                    jenkins._server.reconfig_job(t.name, ET.tostring(root).decode('utf-8'))
                else:
                    flash('未配置crontab', 'warning')
                    t.scheduler_enable = False
                    db.session.commit()
        except ValueError as e:
            t.scheduler_enable = False
            db.session.commit()

            current_app.logger.error('crontab wrong')
            current_app.logger.exception(e)
            flash('crontab格式错误', 'danger')
        except JenkinsException as e:
            current_app.logger.error('jenkins create job error: {}'.format(e))
            flash('内部错误', 'danger')

            try:
                t.scheduler_enable = False
                db.session.commit()
            except NameError:
                pass

        return redirect(url_for('.task_list', project_id=project_id))

    current_app.logger.debug('get {}'.format(url_for('.create', project_id=project_id)))
    return render_template('task/task.html', form=form, can_edit=True)


@task.route('/delete/')
def delete():
    """删除任务。"""
    task_id = request.args.get('task_id', type=int)

    t = Task.query.get(task_id)
    project_id = t.project_id
    p = Project.query.get(project_id)

    if current_user not in p.editors:
        current_app.logger.warning(f'user {current_user} is forbade to delete the task {t}')
        abort(403)

    try:
        jenkins._server.delete_job(t.name)

        for record in t.records:
            db.session.delete(record)

        db.session.delete(t)
        db.session.commit()
    except JenkinsException as e:
        current_app.logger.warning('delete task {} error'.format(t))
        current_app.logger.exception(e)
        flash('内部错误', 'danger')

    return redirect(url_for('.task_list', project_id=project_id))


@task.route('/<task_id>/analysis/')
def analysis(task_id):
    t = Task.query.get(task_id)
    # 按时间顺序提取出任务的执行记录并过滤掉没有统计结果的记录
    records = [record for record in sorted(t.records, key=lambda record: record.timestamp) if
               record.result and record.result.tests]

    # 折线图默认显示版本数
    show_number_default = 10
    # 计算显示窗口
    record_len = len(records)
    if record_len <= show_number_default:
        zoom_start = 0
    else:
        zoom_start = round(show_number_default / record_len * 100)

    version = [record.version for record in records]
    value = [round((record.result.tests - record.result.errors - record.result.skip -
                    record.result.failures) / record.result.tests * 100, 2) for record in records]

    page = request.args.get('page', 1, type=int)

    pagination = Record.query.filter_by(task_id=task_id).order_by(
        Record.timestamp.desc()).paginate(page, per_page=current_app.config['POLARIS_RECORDS_PER_PAGE'],
                                          error_out=False)

    all_records = pagination.items
    return render_template('task/analysis.html', task=t, version=version, value=value, records=all_records,
                           project_id=t.project_id, pagination=pagination, zoom_start=zoom_start)
