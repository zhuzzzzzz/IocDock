1. 基于 nginx 实现 registry push 时的 session 粘性（sticky session）
2. 确定容器服务的重启策略 (always 或 on-failure)
3. 应排除 check_running 运行时会比较的 .iocsh_history文件
4. 部署 registry 前检查证书, 部署registry后设置证书可信, 部署后设置集群节点登录 registry 服务