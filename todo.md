1. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项 
2. 使用 ansible 等工具在装机时为每台主机维护ip、节点标签等信息(/var/tmp/IocDock/NodeInfo)，以供容器或主机通过动态加载方式获取宿主机信息
   ```text
   NODE_IP = <节点ip>
3. 对于ubuntu关闭 snap apt 自动更新