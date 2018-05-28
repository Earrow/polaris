# coding=utf-8

import logging

from flask import render_template, url_for, redirect, flash, request, current_app, abort
from flask_login import current_user, login_required

from . import project
from .forms import ProjectApplyForm, ProjectEditForm
from .. import db
from ..models import Project, RegistrationApplication, ProjectApplication, Server

logger = logging.getLogger('polaris.project')


@project.route('/')
def project_list():
    """项目列表。"""
    logger.debug('get {}'.format(url_for('.project_list')))

    page = request.args.get('page', 1, type=int)
    pagination = Project.query.paginate(page, per_page=current_app.config['POLARIS_PROJECTS_PER_PAGE'], error_out=False)
    p = pagination.items

    # 检查用户是否有申请的项目被拒绝的记录，若有则弹出提示
    if not current_user.is_anonymous:
        applications = ProjectApplication.query.filter_by(user=current_user).filter_by(state=-1).filter_by(
            showed=False).all()
        for application in applications:
            flash('你申请的项目被拒绝，请联系管理员或重新申请', 'warning')
            application.showed = True
        db.session.commit()

    return render_template('project/projects.html', pagination=pagination, projects=p)


@project.route('/<project_id>/', methods=['GET', 'POST'])
def project_info(project_id):
    """项目信息。"""
    form = ProjectEditForm()

    if form.validate_on_submit():
        logger.debug('post {}'.format(url_for('.project_info', project_id=project_id)))

        p = Project.query.get(project_id)
        # 校验当前用户是否有修改项目权限
        if current_user in p.editors:
            logger.debug('user {} edited the project {}'.format(current_user, p))

            p.name = form.name.data
            p.info = form.info.data
            p.server = Server.query.get(form.server_id.data)
            db.session.add(p)
            db.session.commit()

            return redirect(url_for('.project_list'))
        else:
            logger.warning('user {} is not allowed to edit the project {}'.format(current_user, p))
            abort(403)

    logger.debug('get {}'.format(url_for('.project_info', project_id=project_id)))

    p = Project.query.get(project_id)
    form.name.data = p.name
    form.info.data = p.info
    form.server_id.data = p.server_id

    # 获取项目信息，若用户有修改权限，则会显示该项目的服务器信息和修改提交按钮
    if current_user in p.editors:
        logger.debug('user {}, can edit the project {}'.format(current_user, p))
        return render_template('project/project.html', form=form, project=p, can_edit=True)
    else:
        logger.debug('user {}, can\'t edit the project {}'.format(current_user, p))
        return render_template('project/project.html', form=form, project=p, can_edit=False)


@project.route('/delete/')
@login_required
def delete():
    """删除项目。"""
    project_id = request.args.get('project_id', type=int)
    p = Project.query.get(project_id)

    if current_user and current_user in p.editors:
        if current_user.active_project == p:
            current_user.active_project = None

            from itertools import chain
            for pp in chain(current_user.editable_projects, current_user.testable_projects):
                current_user.active_project = pp
                break

        for task in p.tasks:
            db.session.delete(task)

        for application in p.registration_applications:
            db.session.delete(application)

        for application in p.project_applications:
            db.session.delete(application)

        for record in p.records:
            db.session.delete(record)

        db.session.delete(p)
        db.session.commit()
    else:
        abort(403)

    return redirect(url_for('.project_list'))


@project.route('/apply/', methods=['GET', 'POST'])
@login_required
def apply():
    """申请新项目."""
    form = ProjectApplyForm()

    if form.validate_on_submit():
        logger.debug('post {}'.format(url_for('.apply')))

        p = Project(name=form.name.data, info=form.info.data, server=Server.query.get(form.server_id.data))
        application = ProjectApplication(user=current_user, project=p)
        db.session.add(application)
        db.session.commit()

        flash('项目申请已提交，请等待管理员审核', 'info')
        return redirect(url_for('.project_list'))

    logger.debug('get {}'.format(url_for('.apply')))
    return render_template('project/project.html', form=form)


@project.route('/register/')
@login_required
def register():
    project_id = request.args.get('project_id', type=int)
    logger.debug('get {}'.format(url_for('.register', project_id=project_id)))

    p = Project.query.get(project_id)
    if current_user in p.editors or current_user in p.testers:
        logger.debug('user {} is in the project {}, not allowed to register'.format(current_user, p))

        flash('你已加入该项目，请勿重复申请', 'warning')
    elif RegistrationApplication.query.filter_by(user=current_user, project=p, state=0).first():
        logger.debug('user {} has applied the project {}, not allowed to register'.format(current_user, p))

        flash('你已提交过申请，请等待管理员审核', 'warning')
    else:
        logger.info('user {} register the project {}'.format(current_user, p))

        application = RegistrationApplication(user=current_user, project=p)
        db.session.add(application)
        db.session.commit()
        flash('加入申请已提交，请等待管理员审核', 'info')
    return redirect(url_for('.project_list'))


@project.route('/set_active_project/')
def set_active_project():
    project_id = request.args.get('project_id', type=int)
    p = Project.query.get(project_id)

    current_user.active_project = p
    db.session.commit()

    return redirect(url_for('.project_list'))
