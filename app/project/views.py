# coding=utf-8

from flask import render_template, url_for, redirect, flash, request, current_app, abort
from flask_login import current_user, login_required
from jenkins import JenkinsException

from . import project
from .forms import ProjectApplyForm, ProjectEditForm
from .. import db, jenkins
from ..models import Project, RegistrationApplication, ProjectApplication, Server, OperatingRecord


@project.route('/')
def project_list():
    """项目列表。"""
    page = request.args.get('page', 1, type=int)
    current_app.logger.debug('get {}'.format(url_for('.project_list', page=page)))

    pagination = Project.query.paginate(page, per_page=current_app.config['POLARIS_PROJECTS_PER_PAGE'], error_out=False)
    p = pagination.items

    # 检查用户是否有申请的项目被拒绝的记录，若有则弹出提示
    if not current_user.is_anonymous:
        applications = ProjectApplication.query.filter_by(user=current_user).filter_by(state=-1).filter_by(
            showed=False).all()
        for application in applications:
            current_app.logger.info(f'showed disallowed project application: {application}')

            flash('你申请的项目被拒绝，请联系管理员或重新申请', 'warning')
            application.showed = True

        db.session.commit()

    return render_template('project/projects.html', pagination=pagination, projects=p)


@project.route('/<project_id>/', methods=['GET', 'POST'])
def project_info(project_id):
    """项目信息。"""
    form = ProjectEditForm()
    p = Project.query.get(project_id)

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.project_info', project_id=project_id)))

        # 校验当前用户是否有修改项目权限
        if current_user in p.editors:
            try:
                server = Server.query.get(form.server_id.data)
                if p.server != server:
                    # 修改jenkins上任务的测试服务器
                    import xml.etree.ElementTree as ET

                    for task in p.tasks:
                        config = jenkins._server.get_job_config(task.name)
                        root = ET.fromstring(config)

                        root.find('assignedNode').text = server.host
                        jenkins._server.reconfig_job(task.name, ET.tostring(root).decode('utf-8'))

                p.name = form.name.data
                p.info = form.info.data
                p.server = server
                db.session.add(p)
                operating_record = OperatingRecord(user=current_user, operation='修改', project=p)
                db.session.add(operating_record)
                db.session.commit()

                current_app.logger.info(f'user {current_user} edited the project {p}')
            except JenkinsException as e:
                current_app.logger.error('jenkins edit job error')
                current_app.logger.exception(e)
                flash('内部错误', 'danger')

            return redirect(url_for('.project_list'))
        else:
            current_app.logger.warning(f'user {current_user} is forbade to edit the project {p}')
            abort(403)

    current_app.logger.debug('get {}'.format(url_for('.project_info', project_id=project_id)))

    form.name.data = p.name
    form.info.data = p.info
    form.server_id.data = p.server_id

    # 获取项目信息，若用户有修改权限，则会显示该项目的服务器信息和修改提交按钮
    if current_user in p.editors:
        current_app.logger.debug(f'user {current_user}, can edit the project {p}')
        return render_template('project/project.html', form=form, project=p, can_edit=True)
    else:
        current_app.logger.debug(f'user {current_user}, can\'t edit the project {p}')
        return render_template('project/project.html', form=form, project=p, can_edit=False)


@project.route('/delete/')
@login_required
def delete():
    """删除项目。"""
    project_id = request.args.get('project_id', type=int)
    current_app.logger.debug('get {}'.format(url_for('.delete', project_id=project_id)))

    p = Project.query.get(project_id)

    if current_user and current_user in p.editors:
        for task in p.tasks:
            jenkins._server.delete_job(task.name)
            db.session.delete(task)
            current_app.logger.debug(f'deleted task {task}')

        for user in p.active_users:
            from itertools import chain

            user.active_project = None
            current_app.logger.debug(f'user {user}\'s active project is set to None')

            for pp in chain(user.editable_projects, user.testable_projects):
                if pp != p:
                    user.active_project = pp
                    current_app.logger.debug(f'user {user}\'s active project is set to {pp}')
                    break

        for application in p.registration_applications:
            db.session.delete(application)
            current_app.logger.debug(f'deleted registration application {application}')

        for application in p.project_applications:
            db.session.delete(application)
            current_app.logger.debug(f'deleted project application {application}')

        for record in p.records:
            db.session.delete(record.result)
            db.session.delete(record)
            current_app.logger.debug(f'deleted record {record}')

        db.session.delete(p)
        operating_record = OperatingRecord(user=current_user, operation='删除', project=p)
        db.session.add(operating_record)
        db.session.commit()

        current_app.logger.info(f'user {current_user} deleted the project {p}')
    else:
        current_app.logger.warning(f'user {current_user} is forbade to delete the project {p}')
        abort(403)

    return redirect(url_for('.project_list'))


@project.route('/apply/', methods=['GET', 'POST'])
@login_required
def apply():
    """申请新项目."""
    form = ProjectApplyForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.apply')))

        p = Project(name=form.name.data, info=form.info.data, server=Server.query.get(form.server_id.data))
        application = ProjectApplication(user=current_user, project=p)
        db.session.add(application)
        operating_record = OperatingRecord(user=current_user, operation='申请创建', project=p, show_for_admin=True)
        db.session.add(operating_record)
        db.session.commit()

        current_app.logger.info(f'created project application: {application}')
        flash('项目申请已提交，请等待管理员审核', 'info')
        return redirect(url_for('.project_list'))

    current_app.logger.debug('get {}'.format(url_for('.apply')))
    return render_template('project/project.html', form=form)


@project.route('/register/')
@login_required
def register():
    project_id = request.args.get('project_id', type=int)
    current_app.logger.debug('get {}'.format(url_for('.register', project_id=project_id)))

    p = Project.query.get(project_id)
    if current_user in p.editors or current_user in p.testers:
        current_app.logger.info(f'user {current_user} was in the project {p}, disallowed to register')

        flash('你已加入该项目，请勿重复申请', 'warning')
    elif RegistrationApplication.query.filter_by(user=current_user, project=p, state=0).first():
        current_app.logger.info(f'user {current_user} has applied the project {p}, disallowed to register')

        flash('你已提交过申请，请等待管理员审核', 'warning')
    else:
        application = RegistrationApplication(user=current_user, project=p)
        db.session.add(application)
        operating_record = OperatingRecord(user=current_user, operation='申请加入', project=p, show_for_admin=True)
        db.session.add(operating_record)
        db.session.commit()

        current_app.logger.info(f'created registration application: {application}')
        flash('加入申请已提交，请等待管理员审核', 'info')
    return redirect(url_for('.project_list'))


@project.route('/set_active_project/')
def set_active_project():
    project_id = request.args.get('project_id', type=int)
    current_app.logger.debug('get {}'.format(url_for('.set_active_project', project_id=project_id)))

    p = Project.query.get(project_id)

    if current_user in p.testers.all() or current_user in p.editors.all():
        current_user.active_project = p
        db.session.commit()

        current_app.logger.info(f'user {current_user}\'s active project is set to {p}')

    return redirect(url_for('.project_list'))
