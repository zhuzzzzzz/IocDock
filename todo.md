1. 为所有swarm主机添加设置 HOSTNAME=`hostname` 的环境变量初始化设置（done, 通过/etc/hostname解决iocLogServer即可）
2. 将registry portainer服务迁移至 swarm部署，通过placement指定manager或worker，移除compose模式相关代码
3. README文件中固定使用的软件版本，compose文件中固定使用的镜像版本
4. 文件夹名称，目录名称规范定义，在IMConsts.py文件通过设置类型分块定义(done？)
5. 工具名称，文件夹名称重命名
6. 取消工具在命令行中传递项目路径的方式，改为统一在config文件中进行配置
7. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项
8. 显示swarm节点时显示其带有的标签
9. NFS共享目录中其他主机会调用IocManager指令，考虑使用source方式并设置IocManager作为备选默认值
10. 将imtools目录拆分出imsrvs目录以存放服务文件