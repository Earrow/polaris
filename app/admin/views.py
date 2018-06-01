# coding=utf-8

from flask import render_template, redirect, url_for, jsonify, request, current_app
from flask_login import login_required

from . import admin
from .. import db
from ..models import RegistrationApplication, ProjectApplication, Project, Server
from ..decorators import admin_required
from ..project.forms import ProjectApplyForm


@admin.route('/create_project/', methods=['GET', 'POST'])
@login_required
@admin_required
def create_project():
    """创建新项目。"""
    form = ProjectApplyForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.create_project')))

        p = Project(name=form.name.data, info=form.info.data, server=Server.query.get(form.server_id.data))
        p.allowed = True
        db.session.add(p)
        db.session.commit()

        current_app.logger.info(f'created {p}')
        return redirect(url_for('project.project_list'))

    current_app.logger.debug('get {}'.format(url_for('.create_project')))
    return render_template('project/project.html', form=form)


@admin.route('/registration_applications/')
@login_required
@admin_required
def registration_applications():
    """用户加入项目申请列表。"""
    current_app.logger.debug('get {}'.format(url_for('.registration_applications')))

    applications = RegistrationApplication.query.filter_by(state=0).order_by(
        RegistrationApplication.timestamp.desc()).all()

    current_app.logger.debug(f'registration applications: {applications}')
    return render_template('admin/registration_applications.html', applications=applications)


@admin.route('/handle_registration_application/')
@login_required
@admin_required
def registration_applications_handle():
    """处理用户加入项目申请。"""
    application_id = request.args.get('application_id', type=int)
    application_state = request.args.get('application_state')

    current_app.logger.debug('get {}'.format(url_for('.registration_applications_handle', application_id=application_id,
                                                     application_state=application_state)))

    application = RegistrationApplication.query.get(application_id)
    if application_state == 'ok':
        application.state = 1
        application.user.register(application.project)

        current_app.logger.info(f'allow registration application: {application}')
    elif application_state == 'no':
        application.state = -1

        current_app.logger.info(f'disallow registration application: {application}')

    db.session.commit()
    return redirect(url_for('.registration_applications'))


@admin.route('/project_applications')
@login_required
@admin_required
def project_applications():
    """项目申请列表。"""
    current_app.logger.debug('get {}'.format(url_for('.project_applications')))

    applications = ProjectApplication.query.filter_by(state=0).order_by(
        ProjectApplication.timestamp.desc()).all()

    current_app.logger.debug(f'project applications: {applications}')
    return render_template('admin/project_applications.html', applications=applications)


@admin.route('/handle_project_application/')
@login_required
@admin_required
def project_applications_handle():
    """处理项目申请。"""
    application_id = request.args.get('application_id', type=int)
    application_state = request.args.get('application_state')
    current_app.logger.debug('get {}'.format(url_for('.project_applications_handle', application_id=application_id,
                                                     application_state=application_state)))

    application = ProjectApplication.query.get(application_id)
    if application_state == 'ok':
        application.state = 1
        application.project.allowed = True
        application.user.register(application.project, True)
        db.session.add(application.project)

        current_app.logger.info(f'allow project application {application}')
    elif application_state == 'no':
        application.state = -1
        db.session.delete(application.project)

        current_app.logger.info(f'disallow project application {application}')

    db.session.commit()
    return redirect(url_for('.project_applications'))


@admin.route('/get_application_number')
@login_required
@admin_required
def get_application_number():
    current_app.logger.debug(f'get {url_for(".get_application_number")}')

    registration_applications_number = len(RegistrationApplication.query.filter_by(state=0).all())
    project_applications_number = len(ProjectApplication.query.filter_by(state=0).all())

    current_app.logger.info(f'registration applications number: {registration_applications_number}, '
                            f'project applications number: {project_applications_number}')
    return jsonify({'registration_applications_number': registration_applications_number,
                    'project_applications_number': project_applications_number})
