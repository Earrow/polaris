# coding=utf-8

from itertools import chain

from flask import redirect, url_for, render_template, current_app, request
from flask_login import current_user

from . import main
from .forms import ManualForm, EmailTemplateForm
from .. import db
from ..models import Manual, EmailTemplate, OperatingRecord, Project
from ..decorators import admin_required


@main.route('/')
def index():
    page = request.args.get('page', 1, type=int)

    testable_projects = None
    editable_projects = None
    if current_user.is_authenticated:
        testable_projects = current_user.testable_projects or []
        editable_projects = current_user.editable_projects or []

    if testable_projects or editable_projects:
        show_records = True

        pagination = (
            OperatingRecord.query.order_by(OperatingRecord.timestamp.desc()).join(OperatingRecord.target_projects)
            .filter(OperatingRecord.show_for_admin == False)
            .filter(Project.id.in_(p.id for p in chain(editable_projects, testable_projects)))
            .paginate(page,
                      per_page=current_app.config['POLARIS_OPERATING_RECORDS_PER_PAGE'], error_out=False))
        records = pagination.items

        return render_template('main/index.html', operating_records=records, pagination=pagination,
                               show_records=show_records)
    else:
        show_records = False

        return render_template('main/index.html', show_records=show_records)


@main.route('/help/')
def help_page():
    current_app.logger.debug('get {}'.format(url_for('.help_page')))

    manual = Manual.query.order_by(Manual.timestamp.desc()).first()
    return render_template('main/help.html', manual=manual)


@main.route('/help/edit/', methods=['GET', 'POST'])
@admin_required
def help_page_edit():
    form = ManualForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.help_page_edit')))

        m = Manual(body=form.body.data)
        db.session.add(m)
        db.session.commit()

        current_app.logger.info(f'created manual: {m}')
        return redirect(url_for('.help_page'))

    current_app.logger.debug('get {}'.format(url_for('.help_page_edit')))
    manual = Manual.query.order_by(Manual.timestamp.desc()).first()
    if manual:
        form.body.data = manual.body
    return render_template('main/help_edit.html', form=form)


@main.route('/email_template/')
@admin_required
def email_template_page():
    current_app.logger.debug('get {}'.format(url_for('.email_template_page')))

    template = EmailTemplate.query.order_by(EmailTemplate.timestamp.desc()).first()

    current_app.logger.info(f'template: {template}')
    return render_template('main/email_template.html', template=template)


@main.route('/email_template/edit/', methods=['GET', 'POST'])
@admin_required
def email_template_page_edit():
    form = EmailTemplateForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.email_template_page_edit')))

        t = EmailTemplate(body=form.body.data)
        db.session.add(t)
        db.session.commit()

        current_app.logger.info(f'created template: {t}')
        return redirect(url_for('.help_page'))

    current_app.logger.debug('get {}'.format(url_for('.email_template_page_edit')))
    template = EmailTemplate.query.order_by(EmailTemplate.timestamp.desc()).first()
    if template:
        form.body.data = template.body
    return render_template('main/email_template_edit.html', form=form)
