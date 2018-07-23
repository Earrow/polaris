# coding=utf-8


class NestDict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


def get_sftp_file(host, username, password, path, mode='r'):
    """读取sftp文件，存入临时文件中，支持with as协议，退出后自动删除。"""
    import paramiko
    import tempfile
    import time
    import os

    transport = paramiko.Transport((host, 22))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)

    f_dir = tempfile.gettempdir()
    f_path = os.path.join(f_dir, 'polaris_' + str(int(time.time())) + '.ret')
    sftp.get(path, f_path)

    class C:
        def __enter__(self):
            self.f = open(f_path, mode)
            return self.f

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.f.close()
            os.remove(f_path)

    return C()


def gen_analysis_pic(failure_count, success_count, skip_count, error_count):
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')

    from matplotlib import pyplot as plt

    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.figure(figsize=(3, 4))

    labels = []
    sizes = []
    colors = []
    explode = []
    if failure_count:
        labels.append('failures')
        sizes.append(failure_count)
        colors.append('red')
        explode.append(0)
    if success_count:
        labels.append('pass')
        sizes.append(success_count)
        colors.append('yellowgreen')
        explode.append(0)
    if skip_count:
        labels.append('skip')
        sizes.append(skip_count)
        colors.append('lightskyblue')
        explode.append(0)
    if error_count:
        labels.append('errors')
        sizes.append(error_count)
        colors.append('yellow')
        explode.append(0)

    explode = tuple(explode)
    _, _, _ = plt.pie(sizes,
                      explode=explode,
                      labels=labels,
                      colors=colors,
                      autopct='%3.2f%%',  # 数值保留固定小数位
                      shadow=False,  # 无阴影设置
                      startangle=90,  # 逆时针起始角度设置
                      pctdistance=0.6,  # 数值距圆心半径倍数的距离
                      labeldistance=1.2)
    plt.axis('equal')

    figfile = BytesIO()
    plt.savefig(figfile, format='png')
    figfile.seek(0)
    return figfile.getvalue()
