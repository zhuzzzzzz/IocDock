#### 主机环境设置

1. 配置操作系统基本运行环境：如IP，NFS，NTP，SSH等
2. 安装 docker，设置 docker login 镜像仓库
3. 生成 /var/tmp/IocDock/NodeInfo 文件，其中写入   
   ```NODE_IP = <节点ip>```
4.   

#### 工作环境设置

1. 根据变量 IMConfig.MOUNT_PATH 在每个主机建立相同路径的工作目录，通过 git 仓库拉取代码创建的部署文件均存放于此。
2. 对于要部署的 local 类型服务，根据为其设置的主机标签，在对应主机创建所需的挂载目录