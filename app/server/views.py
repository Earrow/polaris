# coding=utf-8

import urllib

import requests
from flask import render_template, url_for, request, current_app, redirect, jsonify, flash
from flask_login import login_required, current_user
from jenkins import NotFoundException, JenkinsException

from . import server
from .forms import ServerCreateForm, ServerEditForm
from .. import db, jenkins
from ..models import Server, OperatingRecord


def _add_credential(host, username, password):
    """向jenkins添加Credentials。"""
    r = requests.get('http://{}:{}@{}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(
        current_app.config['JENKINS_USERNAME'], current_app.config['JENKINS_PASSWORD'],
        current_app.config['JENKINS_HOST']))
    r.raise_for_status()
    crumb = r.text.split(':')

    import hashlib
    m = hashlib.md5()
    m.update(host.encode('utf-8'))
    m.update(username.encode('utf-8'))
    m.update(password.encode('utf-8'))
    credential_id = m.hexdigest()
    data = {
        "": "0",
        "credentials": {
            "scope": "GLOBAL",
            "id": credential_id,
            "username": username,
            "password": password,
            "description": '{}@{}'.format(username, host),
            "$class": "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl"
        }
    }
    r = requests.post('http://{}:{}@{}/credentials/store/system/domain/_/createCredentials'.format(
        current_app.config['JENKINS_USERNAME'], current_app.config['JENKINS_PASSWORD'],
        current_app.config['JENKINS_HOST']), data=urllib.parse.urlencode({'json': data}),
        headers={'Jenkins-Crumb': crumb[1], 'Content-Type': 'application/x-www-form-urlencoded'})
    r.raise_for_status()

    return credential_id


@server.route('/')
def servers():
    current_app.logger.debug('get {}'.format(url_for('.servers')))

    page = request.args.get('page', 1, type=int)
    pagination = Server.query.paginate(page, per_page=current_app.config['POLARIS_SERVERS_PER_PAGE'], error_out=False)
    s = pagination.items
    return render_template('server/servers.html', pagination=pagination, servers=s)


@server.route('/<server_id>/', methods=['GET', 'POST'])
@login_required
def server_info(server_id):
    form = ServerEditForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.server_info', server_id=server_id)))

        try:
            s = Server.query.get(server_id)

            import xml.etree.ElementTree as ET

            config = jenkins._server.get_node_config(s.host)
            root = ET.fromstring(config)

            if form.username.data != s.username or form.password.data != s.password:
                credential_id = _add_credential(form.host.data, form.username.data, form.password.data)
                root.find('launcher').find('credentialsId').text = credential_id

                current_app.logger.debug('user updated')

            if form.workspace.data != s.workspace:
                root.find('remoteFS').text = form.workspace.data

                current_app.logger.debug('workspace updated')

            if form.info.data != s.info:
                root.find('description').text = form.info.data

                current_app.logger.debug('info updated')

            jenkins._server.reconfig_node(s.host, ET.tostring(root).decode('utf-8'))

            s.host = form.host.data
            s.username = form.username.data
            s.password = form.password.data
            s.workspace = form.workspace.data
            s.info = form.info.data
            db.session.add(s)
            operating_record = OperatingRecord(user=current_user, operation='修改', server=s)
            db.session.add(operating_record)
            db.session.commit()

            current_app.logger.info('{} edited the server {}'.format(current_user, s))
        except JenkinsException as e:
            current_app.logger.error('jenkins edit node error')
            current_app.logger.exception(e)
            flash('内部错误', 'danger')

        return redirect(url_for('.servers'))

    current_app.logger.debug('get {}'.format(url_for('.server_info', server_id=server_id)))

    s = Server.query.get(server_id)
    form.host.data = s.host
    form.username.data = s.username
    form.password.data = s.password
    form.workspace.data = s.workspace
    form.info.data = s.info

    return render_template('server/server.html', form=form, server=s)


@server.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    form = ServerCreateForm()

    if form.validate_on_submit():
        current_app.logger.debug('post {}'.format(url_for('.create')))

        try:
            credential_id = _add_credential(form.host.data, form.username.data, form.password.data)
            current_app.logger.debug(f'credential_id: {credential_id}')

            if not jenkins._server.node_exists(form.host.data):
                jenkins._server.create_node(form.host.data, numExecutors=5, nodeDescription=form.info.data,
                                            remoteFS=form.workspace.data, labels=form.host.data, exclusive=True,
                                            launcher='hudson.plugins.sshslaves.SSHLauncher',
                                            launcher_params={'port': 22, 'credentialsId': credential_id,
                                                             'host': form.host.data})

            s = Server(host=form.host.data, username=form.username.data, password=form.password.data,
                       workspace=form.workspace.data, info=form.info.data)
            db.session.add(s)
            operating_record = OperatingRecord(user=current_user, operation='创建', server=s)
            db.session.add(operating_record)
            db.session.commit()

            current_app.logger.debug(f'created server {s}')
        except requests.exceptions.ConnectionError as e:
            current_app.logger.error('jenkins connect error')
            current_app.logger.exception(e)
            flash('内部错误', 'danger')
        except requests.exceptions.HTTPError as e:
            current_app.logger.error('jenkins add credential error')
            current_app.logger.exception(e)
            flash('内部错误', 'danger')
        except JenkinsException as e:
            current_app.logger.error('jenkins create node error')
            current_app.logger.exception(e)
            flash('内部错误', 'danger')

        return redirect(url_for('.servers'))

    current_app.logger.debug('get {}'.format(url_for('.create')))
    return render_template('server/server.html', form=form)


@server.route('/check_state/')
def check_state():
    """检查服务器在线状态。"""
    s = Server.query.get(request.args.get('server_id', type=int))

    try:
        node_info = jenkins._server.get_node_info(s.host)

        if not node_info['offline']:
            s.workspace = node_info['monitorData']['hudson.node_monitors.DiskSpaceMonitor']['path']
            s.info = node_info['description']
            os = node_info['monitorData']['hudson.node_monitors.ArchitectureMonitor']
            disk_space = round(
                node_info['monitorData']['hudson.node_monitors.DiskSpaceMonitor']['size'] / 1024 / 1024 / 1024, 2)
            db.session.commit()

            current_app.logger.debug('{} is online'.format(s))
            return jsonify(state=1, os=os, disk_space=disk_space)
        else:
            current_app.logger.debug('{} is offline'.format(s))
            return jsonify(state=0, os='', disk_space='')
    except NotFoundException:
        current_app.logger.warning(f'server {s} not found')
        return jsonify(state=-1, os='', disk_space='')
    except JenkinsException as e:
        current_app.logger.error('jenkins check node state error')
        current_app.logger.exception(e)
        return jsonify(state=0, os='', disk_space='')


@server.route('/enable/')
@login_required
def enable():
    """连接服务器"""
    server_id = request.args.get('server_id', type=int)
    s = Server.query.get(server_id)
    try:
        jenkins._server.enable_node(s.host)
    except NotFoundException:
        # 平台上配置的服务器不在jenkins时会出现此错误
        pass
    except JenkinsException as e:
        current_app.logger.warning(f'jenkins enable node {s} error')
        current_app.logger.exception(e)
        flash('内部错误', 'danger')

    return redirect(url_for('.servers'))


@server.route('/delete/')
@login_required
def delete():
    """删除服务器。"""
    server_id = request.args.get('server_id', type=int)
    s = Server.query.get(server_id)
    current_app.logger.debug('get {}'.format(url_for('.delete')))

    try:
        jenkins._server.delete_node(s.host)

        projects_name = ', '.join([project.name for project in s.projects])

        operating_record = OperatingRecord(user=current_user, operation='删除', server=s)
        db.session.add(operating_record)
        db.session.delete(s)
        db.session.commit()

        if projects_name:
            flash(f'请重新配置【{projects_name}】项目的测试服务器', 'warning')
        current_app.logger.info(f'{current_user} deleted the server {s}')
    except NotFoundException:
        # 平台上配置的服务器不在jenkins时会出现此错误
        projects_name = ', '.join([project.name for project in s.projects])

        db.session.delete(s)
        db.session.commit()

        if projects_name:
            flash(f'请重新配置【{projects_name}】项目的测试服务器', 'warning')
        current_app.logger.info(f'{current_user} deleted the server {s}')
    except JenkinsException as e:
        current_app.logger.error('jenkins delete node {} error'.format(s))
        current_app.logger.exception(e)
        flash('内部错误', 'danger')

    return redirect(url_for('.servers'))


@server.route('/get_projects_name/')
@login_required
def get_projects_name():
    """获取使用某个服务器的项目名。"""
    server_id = request.args.get('server_id', type=int)
    s = Server.query.get(server_id)
    current_app.logger.debug('get {}'.format(url_for('.get_projects_name', server_id=server_id)))

    return jsonify(projects_name=', '.join([project.name for project in s.projects]))
