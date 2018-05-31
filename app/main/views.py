from flask import redirect, url_for, render_template

from . import main
from .forms import ManualForm, EmailTemplateForm
from .. import db
from ..models import Manual, EmailTemplate
from ..decorators import admin_required


@main.route('/')
def index():
    return redirect(url_for('project.project_list'))


@main.route('/help/')
def help_page():
    manual = Manual.query.order_by(Manual.timestamp.desc()).first()
    return render_template('main/help.html', manual=manual)


@main.route('/help/edit/', methods=['GET', 'POST'])
@admin_required
def help_page_edit():
    form = ManualForm()
    if form.validate_on_submit():
        m = Manual(body=form.body.data)

        db.session.add(m)
        db.session.commit()
        return redirect(url_for('.help_page'))

    manual = Manual.query.order_by(Manual.timestamp.desc()).first()
    if manual:
        form.body.data = manual.body
    return render_template('main/help_edit.html', form=form)


@main.route('/email_template/')
@admin_required
def email_template_page():
    template = EmailTemplate.query.order_by(EmailTemplate.timestamp.desc()).first()
    return render_template('main/email_template.html', template=template)


@main.route('/email_template/edit/', methods=['GET', 'POST'])
@admin_required
def email_template_page_edit():
    form = EmailTemplateForm()

    if form.validate_on_submit():
        m = EmailTemplate(body=form.body.data)

        db.session.add(m)
        db.session.commit()
        return redirect(url_for('.help_page'))

    template = EmailTemplate.query.order_by(EmailTemplate.timestamp.desc()).first()
    if template:
        form.body.data = template.body
    return render_template('main/email_template_edit.html', form=form)
