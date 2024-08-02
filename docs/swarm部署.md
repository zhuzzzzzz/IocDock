# 基于docker swarm的IOC项目部署及管理

有关swarm模式下运行的docker服务的具体部署和管理方法，需要阅读docker官方给出的文档。本文档仅从部署IOC服务的角度给出必要部分的操作步骤及说明。    
[docker官方文档](https://docs.docker.com/manuals/)

## 部署及管理

### 部署及管理swarm节点

swarm推荐至少3个以上的奇数个管理节点，才能最大化发挥swarm集群冗余备份的安全性和可靠性特点。   
因此推荐准备三台服务器分别工作在互不相干的三套机房环境中(包括电源和网络等硬件资源)，以最大程度实现服务冗余备份安全性。

选定一台服务器初始化swarm，并将其他服务器作为管理者添加至swarm集群中，之后将其他服务器作为工作节点添加至swarm集群，以完成swarm集群的初始化。之后即可向其中部署IOC服务。

- 初始化第一个swarm管理节点

  执行该操作将初始化swarm集群，当前主机自动成为管理者。当主机有多网卡时，可能需要特别指定ip地址，以确定docker
  swarm在哪个网络提供服务    
  ```docker swarm init [--advertise-addr <MANAGER-IP>]```


- 加入管理节点或工作节点

  使用对应manager或对应worker的token，分别在其他主机的终端执行如下命令，以加入到当前swarm集群    
  ```docker swarm join --join-token```


- 管理当前节点退出swarm集群

  ```docker swarm leave```    
  节点退出后在节点列表依然存在，只是状态由Ready变为Down，可在管理节点将其手动移出节点列表    
  ```docker node rm```

### 部署全局服务

全局服务会由swarm编排器控制，自动在每个节点都运行一份。

- 首先创建部署全局服务的配置文件。当前运行的全局服务有IOC服务器的日志服务iocLogServer，因此在创建部署文件时需要指定一个EPICS
  base镜像.

  ```IocManager.py swarm --gen-global-compose-file --base-image xxx ```


- 创建配置文件后，执行指令自动部署这些全局服务.

  ```IocManager.py swarm --deploy-global-services ```

### 导出IOC项目至工作目录

IOC项目的创建配置流程与compose部署基本相同，不同之处在于，当IOC项目需要使用swarm模式部署时，IOC配置文件的host字段需要配置为```swarm```，
且当IOC配置完成后，最后运行生成compose部署文件的命令```--gen-com1pose-file```
需要改为生成swarm部署文件的命令```--gen-swarm-file```

```IocManager.py exec --gen-swarm-file --ioc-list IOC [IOC2 IOC3 ...]  ```

执行```--gen-swarm-file```操作后，IOC服务的状态将变为可用的，使用查看swarm模式摘要信息的命令时，可以看到此状态，
只有当IOC项目处于可用的状态时才能将其部署

### swarm集群的管理命令

使用如下命令，以swarm集群作为整体进行管理

- 查看当前所有IOC项目在swarm模式下的摘要信息.   
  ```IocManager.py swarm --show-digest```


- 查看当前在swarm模式下部署的所有服务，要查看详细信息使用""--detail".   
  ```IocManager.py swarm --show-services```     
  ```IocManager.py swarm --show-services --detail```


- 查看当前在swarm模式下部署的节点信息.   
  ```IocManager.py swarm --show-nodes```


- 查看如何加入当前swarm模式.   
  ```IocManager.py swarm --show-tokens```


- 部署所有当前可用但尚未部署的IOC项目.   
  ```IocManager.py swarm --deploy-all-iocs```


- 移除当前swarm模式下部署的所有服务.   
  ```IocManager.py swarm --remove-all-services```

### IOC service管理命令

正确操作管理脚本后，会对IOC项目生成启动docker服务所必须的配置文件以及IOC项目的启动文件。
当该IOC服务被分配到其他主机运行时，要确保其他主机都能访问到IOC项目目录(即其他主机需要mount上IOC项目目录)，
从而获取服务配置文件及IOC项目的启动文件。

使用如下命令，以docker服务(通常为IOC项目)为单位进行管理

- 将目标IOC项目部署至swarm中运行.   
  ```IocManager.py service IOC [IOC2 IOC3 ...] --deploy```


- 查看当前IOC项目的docker服务配置信息.   
  ```IocManager.py service IOC [IOC2 IOC3 ...] --show-config```


- 查看当前IOC项目的docker服务运行信息.   
  ```IocManager.py service IOC [IOC2 IOC3 ...] --show-info```


- 查看当前IOC项目的运行日志(查看终端输出).   
  ```IocManager.py service IOC [IOC2 IOC3 ...] --show-config```


- 移除当前部署的IOC项目.   
  ```IocManager.py service IOC [IOC2 IOC3 ...] --remove```

## swarm集群的备份及恢复

swarm模式下的管理节点使用Raft Consensus Algorithm算法来管理集群状态。
管理节点的个数没有限制，但管理节点的个数增加使系统更安全可靠，但会影响到整体的系统性能，因此应该将二者折中考虑。

RAFT算法需要管理节点的大多数，也被称为法定人数(quorum)，保持在线，才能就集群状态的更新达成一致。
如果swarm集群失去了大多数管理者，则不能对swarm集群进行任何管理操作。但即使失去了大多数管理者，已部署的swarm集群任务仍会在工作节点正常运行。

### 通常情况的恢复

通常情况下，在故障不损失掉大多数管理节点时，swarm具有故障弹性，可以从任意节点数量的暂时性故障(例如机器崩溃或重启)
中恢复，即将自动调度重新部署离线的服务使swarm集群达到期望状态。当故障损失掉大多数管理节点的情况下，swarm的故障弹性将失效，
正在工作的已部署服务会继续运行，但无法执行管理任务。

通常情况下，若有节点故障，最好的恢复方法是将故障的节点重新上线。

- 若无法通过重启故障节点的方式将管理节点恢复至quorum状态，可选择某个正常的管理节点执行如下操作，将swarm集群恢复至只有单个管理节点的初始状态
  (这个管理节点保存有swarm集群之前的服务和任务信息)，再重新添加新管理节点使集群恢复quorum. 
  ```docker swarm init --force-new-cluster```

若所有的管理节点都无法正常恢复(丢失掉了swarm数据)，可以参考后文的灾难恢复部分

### 灾难恢复

管理节点将swarm状态和管理日志存储在```/var/lib/docker/swarm```目录下，这个目录下也存有用来加密RAFT日志的密钥。
没有这些密钥将无法恢复swarm集群。

将这个目录恢复至某个docker服务停止的节点，重启docker服务，执行```docker swarm init --force-new-cluster```
命令完成灾难恢复，将在执行操作的节点上暂时恢复所有swarm状态。

关于当前的恢复操作，管理工具提供了管理命令，可参考后文进行swarm集群的备份与恢复。

### 关于swarm集群的备份恢复命令

管理工具提供了关于swarm进行灾难备份的以及恢复的命令。

- 备份swarm集群配置。需要选择管理节点执行备份，在执行备份时当前管理节点将暂时关闭docker服务，备份结束后将恢复.   
  ```IocManager.py swarm --backup-swarm```


- 恢复swarm集群配置。选择任一节点，指定需要恢复的备份文件，执行恢复.
  ```IocManager.py swarm --restore-swarm --backup-file xxx```

执行灾难恢复时将恢复swarm集群配置，并在新的集群内(通常是当前节点)上线备份状态下运行的所有服务和任务。
原有的集群节点是否能重新连接取决于节点中相关的swarm状态信息是否仍存在，当原有节点无法连接时，应手动删除无法连接的节点并添加新的节点。
完成节点设置后可以使用命令将当前运行的服务重新编排部署至各个节点，以完成对资源的均衡利用。

- 更新swarm部署状态，将服务分发至各个节点运行.