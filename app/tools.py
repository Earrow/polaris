# coding=utf-8


class NestDict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


def get_sftp_file(host, username, password, path):
    """读取sftp文件，存入临时文件中，支持with as协议，退出后自动删除。"""
    import paramiko
    import tempfile
    import time
    import os

    transport = paramiko.Transport((host, 22))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)

    f_dir = tempfile.gettempdir()
    f_path = os.path.join(f_dir, 'polaris_'+str(int(time.time()))+'.ret')
    sftp.get(path, f_path)

    class C:
        def __enter__(self):
            self.f = open(f_path)
            return self.f

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.f.close()
            os.remove(f_path)

    return C()
