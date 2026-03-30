# IocDock

**为大型科学装置控制系统设计的 IOC(Input/Output Controller) 应用程序容器化部署管理系统.**

**基于 EPICS 架构的 IOC 部署管理平台, 提供 IOC 项目开发构建、应用程序部署管理及运维监控相关自动化功能.**

- 基于 docker swarm 的高可用性部署
- 基于 ansible 的集群自动化运维配置
- 基于 prometheus 的运行指标监控报警
- 基于 loki 的运行日志监控报警
- 基于 grafana 的数据可视化监控

## Getting Started

### 1. 安装

#### 基于 git 快速安装

```shell
# 在管理主机拉取代码以安装部署管理系统
$ git clone https://github.com/zhuzzzzzz/IocDock.git

# 安装依赖的 python 包
$ pip install -r requirments.txt
# 若提示 python 包由系统包管理器管理, 可分别执行 apt install python-package_name 完成安装

# 安装工具, 并重启终端使配置生效
$ sudo ./install.sh
```

**关于如何安装或升级系统工具, 详见文档 `系统部署指南.md` .**

### 2. 构建集群环境

**关于如何构建集群环境, 见文档 `系统部署指南.md` .**

### 3. 部署集群基础设施服务

**关于如何部署预置的集群基础设施服务, 见文档 `系统部署指南.md` .**

| 系统基础服务 | 访问地址 |
| ------------ | ------- |
| registry | `https://node_ip:443` |
| prometheus | `http://node_ip:9090` |
| alertManager | `http://node_ip:9093` |
| loki | `http://node_ip:3100` |
| grafana | `http://node_ip:3000` |
| alloy | `http://node_ip:12345` |
| cAdvisor | `http://node_ip:8080` |
| node-exporter | `http://node_ip:9100` |
| iocLogServer | `http://node_ip:7004` |
| alertAnalytics | `http://node_ip:8000` |

### 4. 部署 IOC 服务

#### 4.1 部署测试环境 IOC 项目

```shell
# 运行脚本生成测试 IOC 项目
$ cd docker/IocDock
$ ./make-test-project.sh make

# 部署 IOC 项目至工作节点
$ IocManager swarm --deploy-all-iocs

# 查看正在运行的 IOC
$ IocManager list -p
IOC            Host   Description                               State   Status    DeployStatus            SnapshotConsistency  RuningConsistency
worker_test_1  swarm  IOC that implements a ramper for test...  normal  exported  Running 9 seconds ago   consistent           consistent
worker_test_2  swarm  IOC that implements a ramper for test...  normal  exported  Running 10 seconds ago  consistent           consistent
worker_test_3  swarm  IOC that implements a ramper for test...  normal  exported  Running 10 seconds ago  consistent           consistent
worker_test_4  swarm  IOC that implements a ramper for test...  normal  exported  Running 10 seconds ago  consistent           consistent
worker_test_5  swarm  IOC that implements a ramper for test...  normal  exported  Running 10 seconds ago  consistent           consistent

# 验证 IOC 是否正常工作
$ IocManager client caget ramper:worker_test_1
executing "docker exec 80ba9296482b ./caget ramper:worker_test_1".
ramper:worker_test_1           6
```

#### 4.2 部署生产环境 IOC 项目

**关于如何开发及部署生产环境 IOC 项目, 见文档 `系统部署指南.md` 与 `系统管理指南.md` .**

### 5. 管理 IOC 项目与容器服务

**关于如何管理系统内已部署的 IOC 项目与容器服务, 见文档 `系统管理指南.md` .**

#### 5.1 查看 IOC 基本信息

```shell
# 列出所有IOC
$ IocManager list
worker_test_1 worker_test_2 worker_test_3 worker_test_4 worker_test_5

# 列出所有IOC并显示其描述信息
$ IocManager list -d
IOC            Description
worker_test_1  IOC that implements a ramper for testing.
worker_test_2  IOC that implements a ramper for testing.
worker_test_3  IOC that implements a ramper for testing.
worker_test_4  IOC that implements a ramper for testing.
worker_test_5  IOC that implements a ramper for testing.

# 列出所有IOC并显示其项目状态
# SnapshotConsistency表当前仓库文件与快照文件的一致性
# RunningConsistency表当前仓库文件与运行文件的一致性
$ IocManager list -p
IOC            Host    Description                               State    Status    DeployStatus            SnapshotConsistency    RunningConsistency
worker_test_1  swarm   IOC that implements a ramper for test...  normal   exported  Running 38 minutes ago  consistent             consistent
worker_test_2  swarm   IOC that implements a ramper for test...  normal   exported  Running 38 minutes ago  consistent             consistent
worker_test_3  swarm   IOC that implements a ramper for test...  normal   exported  Running 38 minutes ago  consistent             consistent
worker_test_4  swarm   IOC that implements a ramper for test...  normal   exported  Running 38 minutes ago  consistent             consistent
worker_test_5  swarm   IOC that implements a ramper for test...  normal   exported  Running 38 minutes ago  consistent             consistent
```

#### 5.2 连接系统内运行的 IOC PV

```shell
# 系统内在所有节点部署了 client 容器, 可使用该容器代理 EPICS client 请求
$ IocManager client caget pv_name
$ IocManager client caput pv_name
$ IocManager client cainfo pv_name
$ IocManager client camonitor pv_name
```

#### 5.3 查看 swarm 集群基本信息

```shell
# 显示系统管理的 swarm 集群摘要信息
$ IocManager swarm --show-digest
Name           ServiceName             Type    Replicas    Status
alertManager   iasf_srv-alertManager   local   3/3         Running 4 hours ago
grafana        iasf_srv-grafana        local   1/1         Running 5 hours ago
loki           iasf_srv-loki           local   1/1         Running 5 hours ago
prometheus     iasf_srv-prometheus     local   1/1         Running 5 hours ago
registry       iasf_srv-registry       local   3/3         Running 5 hours ago
alloy          iasf_srv-alloy          global  6/6         Running 5 hours ago
cAdvisor       iasf_srv-cAdvisor       global  6/6         Running 5 hours ago
client         iasf_srv-client         global  6/6         Running 5 hours ago
iocLogServer   iasf_srv-iocLogServer   global  6/6         Running 5 hours ago
nodeExporter   iasf_srv-nodeExporter   global  6/6         Running 5 hours ago
hello          iasf_srv-hello          custom  -/-         Available. Not deployed
worker_test_1  iasf_srv-worker_test_1  ioc     1/1         Running 4 hours ago
worker_test_2  iasf_srv-worker_test_2  ioc     1/1         Running 4 hours ago
worker_test_3  iasf_srv-worker_test_3  ioc     1/1         Running 4 hours ago
worker_test_4  iasf_srv-worker_test_4  ioc     1/1         Running 4 hours ago
worker_test_5  iasf_srv-worker_test_5  ioc     1/1         Running 4 hours ago


# 显示系统内部署的所有集群节点及其详细信息
$ IocManager swarm --show-nodes --detail
HOSTNAME         STATUS    AVAILABILITY   MANAGER STATUS   TLS STATUS   ENGINE VERSION
swarm-manager    Ready     Active         Reachable        Ready        28.3.2
swarm-manager1   Ready     Active         Reachable        Ready        28.3.3
swarm-node0      Ready     Active                          Ready        28.3.2
swarm-node1      Ready     Active                          Ready        28.3.2
*ubuntu-new*     Ready     Active         Reachable        Ready        28.3.3
ubuntu-server    Ready     Active         Leader           Ready        28.3.2

------------
Node Details:
------------
swarm-manager(192.168.1.52):    alertmanager=true registry=true
swarm-manager1(192.168.1.55):   alertmanager=true registry=true
swarm-node0(192.168.1.53):
swarm-node1(192.168.1.54):
ubuntu-new(192.168.1.51):
ubuntu-server(192.168.1.50):    alertmanager=true grafana=true loki=true prometheus=true registry=true
```

## 项目目录结构说明

**详见文档 `项目结构.md` .**

## 更新日志及功能说明

======= 2026/03/30 =======
