# coding=utf-8

import json
from urllib import request
from functools import wraps


def report(host, project_name, task_name):
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


if __name__ == '__main__':
    @report('127.0.0.1:5000', 'intent', 't')
    def fun():
        return 1, 2, 3, 4

    fun()

