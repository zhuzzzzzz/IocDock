# 部署swarm

有关swarm模式的具体部署和管理方法，可参考docker官方给出的文档。本文档仅从部署IOC服务的角度给出必要的操作步骤及说明。

### 管理swarm节点

##### 初始化第一个swarm管理节点

docker swarm init [ --advertise-addr <MANAGER-IP> ]    
当主机有多网卡时，可能需要特别指定ip地址，以确定docker swarm在哪个网络提供服务

##### 加入管理节点或工作节点

docker swarm join --join-token

##### 当前节点退出swarm

docker swarm leave

节点退出后在节点列表依然存在，只是状态由Ready变为Down，可在管理节点将其手动移出节点列表    
docker node rm

### 部署及管理IOC服务

##### 部署全局服务

首先创建全局服务部署文件。全局服务会自动在每个节点都运行一份，当前运行的全局服务有iocLogServer，
因此在创建全局服务部署文件时需要指定一个EPICS base镜像.

```./IocManager.py swarm --gen-global-compose-file --base-image xxx ```

创建全局服务部署文件后，可执行指令自动部署这些全局服务.

```./IocManager.py swarm --deploy-global-services ```

若要移除部署的公共服务，参考docker在swarm部署模式下的官方文档.

##### 导出IOC项目至工作目录

IOC创建配置流程与compose部署基本相同，不同之处在于，当IOC需要使用swarm模式部署时，IOC配置文件的host字段需要配置为"swarm"，
且当IOC配置完成后，最后运行的生成compose部署文件命令"--gen-compose-file"此时变更为生成swarm部署文件命令"
--gen-swarm-file"。

```./IocManager.py exec --gen-swarm-file --ioc-list IOC [IOC2 IOC3 ...]  ```

##### swarm管理命令

- 查看当前所有IOC项目在swarm模式下的摘要信息.   
  ```./IocManager.py swarm --show-digest```

- 查看当前在swarm模式下部署的所有服务，要查看详细信息使用""--detail".   
  ```./IocManager.py swarm --show-services```   
  ```./IocManager.py swarm --show-services --detail```

- 查看当前在swarm模式下部署的节点信息.   
  ```./IocManager.py swarm --show-nodes```

- 查看如何加入当前swarm模式.   
  ```./IocManager.py swarm --show-tokens```

##### IOC service管理命令

