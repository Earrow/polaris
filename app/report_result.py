# coding=utf-8

import json
from urllib import request
from functools import wraps


def report(host, project_name, task_name):
    """将测试结果上报给平台，测试结果由用户统计并将统计函数注册在该函数下。

    :param host: polaris平台地址。
    :param project_name: 项目名。
    :param task_name: 测试任务名。
    :return: 测试用例数量、出错数量、失败数量、跳过执行数量组成的元组。

    示例：
    >>> @report('127.0.0.1:5000', 'Test', 't')
    ... def result_statistics():
    ...    tests = 5
    ...    errors = 1
    ...    failures = 1
    ...    skip = 0
    ...    return tests, errors, failures, skip

    >>> result_statistics()  # 执行统计脚本的命令需在创建任务时的结果统计栏填写
    """
    url = 'http://{}/records/report_result'.format(host)

    def out_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tests, errors, failures, skip = func(*args, **kwargs)

            data = {
                'project_name': project_name,
                'task_name': task_name,
                'tests': tests,
                'errors': errors,
                'failures': failures,
                'skip': skip
            }

            req = request.Request(url, data=json.dumps(data).encode('utf-8'))
            request.urlopen(req)

        return wrapper

    return out_wrapper
