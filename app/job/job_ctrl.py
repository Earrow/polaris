# coding=utf-8

"""
deprecated.
"""

import pickle
from threading import Thread
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import redis
import paramiko

r = redis.Redis('localhost')
r.delete('polaris:results')
executor = ThreadPoolExecutor(5)


def execute(hostname, username, password, commands, project_id=None, task_id=None, record_id=None):
    """连接服务器执行测试任务。

    :param hostname: 服务器地址
    :param username: 服务器用户名
    :param password: 服务器密码
    :param commands: 命令列表
    :param project_id: 项目id，定时任务需要传入该参数
    :param task_id: 任务id，定时任务需要传入该参数
    :param record_id: 执行记录id，手动任务需要传入该参数
    :return: 命令执行结果状态码和执行结果列表组成的元组
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=hostname, username=username, password=password)

    stdin, stdout, stderr = ssh.exec_command(';'.join(commands))
    execute_result = []
    execute_time = datetime.utcnow()

    def f1():
        for line in stdout:
            execute_result.append(line.strip())

    def f2():
        for line in stderr:
            execute_result.append(line.strip())
        ssh.close()
        return

    t1 = Thread(target=f1)
    t2 = Thread(target=f2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    ssh.close()

    status = stdout.channel.recv_exit_status()
    cmd_line = '<br>'.join(['>> ' + line for line in execute_result])
    cmd_line += '<br><br> exit status: {}'.format(status)

    if record_id:
        r.hset('polaris:results', record_id, pickle.dumps({'cmd_line': cmd_line, 'status': status}))
    elif project_id and task_id:
        execute_record = {
            'project_id': project_id,
            'task_id': task_id,
            'execute_time': execute_time,
            'cmd_line': cmd_line,
            'status': status
        }
        r.rpush('polaris:results_on_time', pickle.dumps(execute_record))
    else:
        raise ValueError


def register(hostname, username, password, commands, record_id):
    """注册测试任务。"""
    t = Thread(target=execute, args=(hostname, username, password, commands, None, None, record_id), daemon=True)
    t.start()
