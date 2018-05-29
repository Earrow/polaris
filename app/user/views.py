# encoding=utf-8

import logging

from flask import request, url_for, render_template, jsonify, abort, redirect, flash
from flask_login import current_user

from . import user
from .forms import AddUserForm
from .. import db
from ..models import User, Project, RegistrationApplication

logger = logging.getLogger('polaris.user')


@user.route('/', methods=['GET', 'POST'])
def user_list():
    project_id = request.args.get('project_id', type=int)
    p = Project.query.get(project_id)

    if current_user not in p.editors:
        abort(403)

    form = AddUserForm()
    if form.validate_on_submit():
        logger.debug('post {}'.format(url_for('.user_list', project_id=project_id)))

        email = form.new_user_email.data
        permission = form.new_user_permission.data
        logger.debug(f'email: {email}, permission: {permission}')

        u = User.query.filter_by(email=email).first()
        if u:
            if u not in p.editors.all() and u not in p.testers.all():
                u.register(p, True if permission == 'editor' else False)

            if u in p.editors.all() and permission == 'tester':
                p.editors.remove(u)
                u.editable_projects.remove(p)
                p.testers.append(u)

            if u in p.testers.all() and permission == 'editor':
                p.testers.remove(u)
                u.testable_projects.remove(p)
                p.editors.append(u)

            application = RegistrationApplication.query.filter_by(user=u, project=p, state=0).first()
            if application:
                application.state = 1

            db.session.commit()
            logger.debug(f'add {u} to {p}')
        else:
            flash('添加用户不存在', 'danger')
        return redirect(url_for('.user_list', project_id=project_id))

    logger.debug('get {}'.format(url_for('.user_list', project_id=project_id)))

    users = [u for u in p.editors.all() + p.testers.all() if u.role.name != 'Administrator' and u != current_user]
    return render_template('user/users.html', users=users, project=p, form=form)


@user.route('/change_permission')
def change_permission():
    """修改用户权限。"""
    user_id = request.args.get('user_id', type=int)
    project_id = request.args.get('project_id', type=int)
    check_val = request.args.get('check_val', type=str)
    logger.debug(
        'get {}'.format(url_for('.change_permission', user_id=user_id, project_id=project_id, check_val=check_val)))

    u = User.query.get(user_id)
    p = Project.query.get(project_id)

    if current_user not in p.editors:
        logger.warning(f'{current_user} change permission forbidden')
        abort(403)

    if check_val == 'editor':
        p.testers.remove(u)
        u.testable_projects.remove(p)
        p.editors.append(u)
    elif check_val == 'tester':
        p.editors.remove(u)
        u.editable_projects.remove(p)
        p.testers.append(u)

    db.session.commit()
    return jsonify(status=0)


@user.route('/remove')
def remove():
    """将用户从项目中移除。"""
    user_id = request.args.get('user_id', type=int)
    project_id = request.args.get('project_id', type=int)
    logger.debug(
        'get {}'.format(url_for('.remove', user_id=user_id, project_id=project_id)))

    u = User.query.get(user_id)
    p = Project.query.get(project_id)

    if current_user not in p.editors:
        logger.warning(f'{current_user} remove user forbidden')
        abort(403)

    if u in p.testers.all():
        p.testers.remove(u)
        u.testable_projects.remove(p)
    else:
        p.editors.remove(u)
        u.editable_projects.remove(p)

    if u.active_project == p:
        u.active_project = None
        p.active_users.remove(u)

    db.session.commit()
    return redirect(url_for('.user_list', project_id=project_id))
