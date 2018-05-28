# Polaris
基于Jenkins的自动化测试平台，工程使用Python3.6+Flask开发。

Polaris是一个集项目管理、测试任务管理、服务器管理及结果统计于一体的自动化测试平台，由于对Jenkins的集成，平台支持各种测试工具的调度、执行。

## 安装
```
>>> pip3 install -r requirements.txt
```
另需安装flask-jenkins模块，参见：https://github.com/Earrow/flask-jenkins
Jenkins平台需安装PostBuildScript 2.7.0插件

## 体验使用
进入项目目录，执行如下指令后，浏览器打开：http://127.0.0.1:5000 进入平台：
```
>>> python3 manage.py shell
>>> db.create_all()
>>> Role.insert_roles()
>>> Manual.insert_manual()

>>> python3 manage.py runserver
```

## 概要介绍
首页即项目管理页面，展示了项目上创建的所有项目，若需要查看、编辑或执行某个项目下的测试任务需先加入该项目然后将该项目设置为活动项目，当前活动项目的查看和更改显示在右上方。
![image](https://github.com/Earrow/polaris/blob/master/images/%E9%A6%96%E9%A1%B5.png)

创建项目需填写项目名、说明、测试服务器，其中服务器需先在基础管理-服务器管理中单独配置。
![image](https://github.com/Earrow/polaris/blob/master/images/project-info.png)

服务器管理，展示平台中配置的所有测试服务器信息，可供在创建项目时选择。
![image](https://github.com/Earrow/polaris/blob/master/images/server-info.png)

测试执行页展示当前项目中配置的所有测试任务，可配置任务、执行测试或查看任务的历史统计数据。
![image](https://github.com/Earrow/polaris/blob/master/images/task.png)

创建任务需填写任务名、说明、执行命令、结果统计、定时设置。执行命令即在测试服务器中执行测试工具的shell命令；当需要平台进行图形化的结果统计时，可遵循平台的结果统计协议编写统计脚本，执行命令在结果统计中填写，详情参考report_result.py。
![image](https://github.com/Earrow/polaris/blob/master/images/task-info.png)

单次执行结果统计。
![image](https://github.com/Earrow/polaris/blob/master/images/task-result.png)

历史执行结果统计。
![image](https://github.com/Earrow/polaris/blob/master/images/task-result-all.png)
