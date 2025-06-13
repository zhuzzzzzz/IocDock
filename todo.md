1. README文件中固定使用的软件版本，compose文件中固定使用的镜像版本
2. 工具名称，文件夹名称重命名
3. 处理base镜像及ioc镜像的Dockerfile中ENTRYPOINT CMD与compose文件中ENTRYPOINT CMD设置项 
4. 使用 ansible 等工具在装机时为每台主机维护ip、节点标签等信息(/var/tmp/IocDock/NodeInfo)，以供容器或主机通过动态加载方式获取宿主机信息
   ```text
   NODE_IP = <节点ip>
5. 优化程序运行的verbose展示, 明确用户只看到必要的成功或失败消息, 其余状态均由verbose显示(done)
6. 优化项目一致性检测功能，分级展示存在的差异文件以及具体文件的差异内容
7. 测试工具的各个功能，并添加测试文档记录工具使用各种情况下的测试构建流程
8. 优化list -p 面板及 swarm --show-digest 面板以展示IOC描述信息或描述信息的截取字符串
