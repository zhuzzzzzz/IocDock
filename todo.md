1. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项
2. 对ansible inventory清单中的非集群主机也开发初始环境配置脚本
3. 解决httpd:2镜像拉取问题
4. 设置registry-data目录自动挂载
5. 解决setup-certs.sh无法通过ansible批量执行
6. 使用自定义文件实现变量覆盖需要处理相关变量的所有二次引用变量定义问题