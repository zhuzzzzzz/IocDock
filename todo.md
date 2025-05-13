1. 为所有swarm主机添加设置 HOSTNAME=`hostname` 的环境变量初始化设置
2. 将registry portainer服务迁移至 swarm部署，通过placement指定manager或worker，移除compose模式相关代码
