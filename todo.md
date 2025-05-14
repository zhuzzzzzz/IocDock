1. 为所有swarm主机添加设置 HOSTNAME=`hostname` 的环境变量初始化设置
2. 将registry portainer服务迁移至 swarm部署，通过placement指定manager或worker，移除compose模式相关代码
3. README文件中固定使用的软件版本，compose文件中固定使用的镜像版本
4. 文件夹名称，目录名称规范定义，在IMConsts.py文件通过设置类型分块定义，并明确哪些是固定项还是可配置的修改项
5. 工具名称，文件夹名称重命名