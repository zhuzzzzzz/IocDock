# IocDock

**为大型科学装置控制系统设计的 IOC(Input/Output Controller) 应用程序容器化部署管理系统.**

**基于 EPICS 架构的 IOC 部署管理平台, 提供 IOC 项目开发构建、应用程序部署管理及运维监控相关自动化功能.**

- 基于 docker swarm 的高可用性部署
- 基于 prometheus 的运行指标监控报警
- 基于 loki 的运行日志监控报警
- 基于 grafana 的数据可视化监控
- 基于 ansible 的集群自动化运维
- 其他控制系统相关的应用程序服务集成

## 安装

```shell
# 拉取代码
git clone https://github.com/zhuzzzzzz/IocDock.git

# 安装工具
# 注意: 安装将创建 用户id=9981 组id=9981 的系统用户, 请确保集群内其他主机均未占用相关编号!
cd IocDock
sudo ./install.sh

# 多用户配置(为本机其他用户配置工具的执行权限)
sudo usermod -aG iocdock $USER
sudo newgrp iocdock
```

## 部署

**关于如何构建系统运行环境, 见文档`系统部署指南.md`.**

**关于如何开发 IOC 项目, 见文档`IOC开发指南`.**

**关于如何管理系统内部署的服务, 见文档`系统管理指南.md`.**

**关于项目架构, 见文档`项目架构.md`.**

## 说明

### 基础设施服务

| 系统服务 | 访问地址 | 说明 |
| ------- | ------- | ------- |
| registry | `https://node_ip:443` | 集群镜像仓库 |
| prometheus | `http://node_ip:9090` | prometheus 服务 |
| alertManager | `http://node_ip:9093` | prometheus 组件 |
| loki | `http://node_ip:3100` | 集群日志采集后端 |
| grafana | `http://node_ip:3000` | 集群数据可视化服务 |
| alloy | `http://node_ip:12345` | 集群日志采集前端 |
| cAdvisor | `http://node_ip:8080` | 集群容器资源监控服务 |
| node-exporter | `http://node_ip:9100` | 集群节点资源监控服务 |
| iocLogServer | `http://node_ip:7004` | IOC 日志采集服务 |
| alertAnalytics | `http://node_ip:8000` | 自定义报警分析服务 |
| dbwr | `http://node_ip:8088` | Display Builder Web Runtime, 基于 WEB 的 PV opi 实时监控服务 |

## 更新日志及功能说明

======= 2026/05/20 =======
