# coding=utf-8

from flask import render_template, url_for, request, redirect, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from . import auth
from .. import db
from .forms import LoginForm, RegistrationForm
from ..models import User


@auth.route('/login/', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.login')))

        user = User.query.filter_by(email=form.email.data).first()
        if user and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)

            current_app.logger.info(f'user {user} login')
            return redirect(request.args.get('next') or url_for('main.index'))

        current_app.logger.info(f'user {user} login failed, email or password wrong')
        flash('账号或密码错误', 'danger')

    current_app.logger.debug('get {}'.format(url_for('.login')))
    return render_template('auth/login.html', form=form)


@auth.route('/logout/')
@login_required
def logout():
    current_app.logger.debug('get {}'.format(url_for('.logout')))

    logout_user()

    current_app.logger.info(f'user {current_user} logout')
    return redirect(url_for('main.index'))


@auth.route('/register/', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.register')))

        user = User(email=form.email.data, password=form.password.data)
        db.session.add(user)

        current_app.logger.info(f'user {user} registered')
        flash('注册成功，请登录', 'success')
        return redirect(url_for('.login'))

    current_app.logger.debug('get {}'.format(url_for('.register')))
    return render_template('auth/register.html', form=form)
