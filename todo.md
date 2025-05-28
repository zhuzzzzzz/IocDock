1. 将registry portainer服务迁移至 swarm部署，通过placement指定manager或worker，移除compose模式相关代码 
2. README文件中固定使用的软件版本，compose文件中固定使用的镜像版本 
3. 工具名称，文件夹名称重命名 
4. 取消工具在命令行中传递项目路径的方式，改为统一在config文件中进行配置 
5. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项 
6. NFS共享目录中其他主机会调用IocManager指令，考虑使用source方式并设置IocManager作为备选默认值(done, registry使用RegistryVar向shell脚本传递工具内变量)
