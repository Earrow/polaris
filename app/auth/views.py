# coding=utf-8

import logging

from flask import render_template, url_for, request, redirect, flash
from flask_login import login_user, logout_user, login_required, current_user

from . import auth
from .. import db
from .forms import LoginForm, RegistrationForm
from ..models import User

logger = logging.getLogger('polaris.auth')


@auth.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        logger.debug('post {}'.format(url_for('.login')))

        user = User.query.filter_by(email=form.email.data).first()
        if user and user.verify_password(form.password.data):
            logger.debug('user {} login'.format(user))

            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('project.project_list'))
        logger.debug('user {} fail to login'.format(user))
        flash('账号或密码错误', 'danger')

    logger.debug('get {}'.format(url_for('.login')))
    return render_template('auth/login.html', form=form)


@auth.route('/logout/')
@login_required
def logout():
    logger.debug('get {}'.format(url_for('.logout')))
    logger.debug('user {} logout'.format(current_user))
    logout_user()
    return redirect(url_for('project.project_list'))


@auth.route('/register/', methods=['GET', 'POST'])
def register():
    logger.debug('post {}'.format(url_for('.register')))
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(email=form.email.data, password=form.password.data)
        logger.debug('user {} registered'.format(user))
        db.session.add(user)
        flash('注册成功，请登录', 'success')
        return redirect(url_for('.login'))

    logger.debug('get {}'.format(url_for('.register')))
    return render_template('auth/register.html', form=form)
