1. 将portainer服务迁移至 swarm部署，通过placement指定manager或worker，移除compose模式相关代码(done)
2. README文件中固定使用的软件版本，compose文件中固定使用的镜像版本
3. 工具名称，文件夹名称重命名
4. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项
5. 使用 ansible 等工具在装机时为每台主机维护ip、节点标签等信息(/var/tmp/IocDock/NodeInfo)，以供容器或主机通过动态加载方式获取宿主机信息
   ```text
   NODE_IP = <节点ip>
   
6. 优化程序运行的verbose展示, 明确用户只看到必要的成功或失败消息, 其余状态均由verbose显示
7. 将IOC状态管理与IOC配置文件解耦(done)