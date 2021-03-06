# coding=utf-8

from flask import render_template, redirect, url_for, jsonify, request, current_app
from flask_login import login_required, current_user

from . import admin
from .. import db
from ..models import RegistrationApplication, ProjectApplication, Project, Server, OperatingRecord, User
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
        operating_record = OperatingRecord(user=current_user, operation='创建', project=p)
        db.session.add(operating_record)
        db.session.commit()

        current_app.logger.info(f'{current_user} created {p}')
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
        operating_record = OperatingRecord(user=current_user, operation='批准加入申请', project=application.project,
                                           show_for_admin=True)

        current_app.logger.info(f'allow registration application: {application}')
    else:  # application_state == 'no'
        application.state = -1
        operating_record = OperatingRecord(user=current_user, operation='拒绝加入申请', project=application.project,
                                           show_for_admin=True)

        current_app.logger.info(f'disallow registration application: {application}')

    db.session.add(operating_record)
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

        operating_record = OperatingRecord(user=current_user, operation='批准创建申请', project=application.project,
                                           show_for_admin=True)

        current_app.logger.info(f'allow project application {application}')
    else:  # application_state == 'no'
        application.state = -1
        db.session.delete(application.project)

        operating_record = OperatingRecord(user=current_user, operation='拒绝创建申请', project=application.project,
                                           show_for_admin=True)

        current_app.logger.info(f'disallow project application {application}')

    db.session.add(operating_record)
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


@admin.route('/operating_records')
@login_required
@admin_required
def operating_records():
    page = request.args.get('page', 1, type=int)
    user = request.args.get('user', '')
    operation = request.args.get('operation', '')
    current_app.logger.debug(f'get {url_for(".operating_records", page=page, user=user, operation=operation)}')

    u = User.query.filter_by(email=user).first()

    if u and operation:
        pagination = (OperatingRecord.query.order_by(OperatingRecord.timestamp.desc())
                      .filter_by(user=u, operation=operation)
                      .paginate(page,
                                per_page=current_app.config['POLARIS_OPERATING_RECORDS_PER_PAGE'], error_out=False))
    elif u:
        pagination = (OperatingRecord.query.order_by(OperatingRecord.timestamp.desc())
                      .filter_by(user=u)
                      .paginate(page,
                                per_page=current_app.config['POLARIS_OPERATING_RECORDS_PER_PAGE'], error_out=False))
    elif operation:
        pagination = (OperatingRecord.query.order_by(OperatingRecord.timestamp.desc())
                      .filter_by(operation=operation)
                      .paginate(page,
                                per_page=current_app.config['POLARIS_OPERATING_RECORDS_PER_PAGE'], error_out=False))
    else:
        pagination = (OperatingRecord.query.order_by(OperatingRecord.timestamp.desc())
                      .paginate(page,
                                per_page=current_app.config['POLARIS_OPERATING_RECORDS_PER_PAGE'], error_out=False))
    records = pagination.items
    return render_template('admin/operating_records.html', operating_records=records, pagination=pagination,
                           filter_user=user, filter_operation=operation)
