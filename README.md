# IocDock

**为加速器控制系统设计的 IOC(Input/Output Controller) 应用程序容器化部署管理系统.**   
**基于 EPICS 架构的 IOC 部署管理平台, 为控制系统提供 IOC 项目开发构建、部署运维、监控管理等各方面的自动化功能.**

- 控制系统服务器集群运行环境构建及管理
- IOC 项目管理
- IOC 容器镜像构建
- 基于容器编排的 IOC 自动化部署及管理
- 基于 Prometheus 的运行指标监控与报警
- 基于 Loki 的运行日志监控与报警
- 基于 Ansible 的集群自动化配置及运维

## Getting Started

### 1. 安装工具

```shell
# 选择一台管理主机, 拉取代码以安装部署管理系统
git clone https://github.com/zhuzzzzzz/IocDock.git

# 安装依赖的 python 包
pip install -r requirments.txt

# 安装工具
sudo ./install.sh

# 重启完成安装
reboot

# 运行以下命令, 若无报错则搭建成功
IocManager list
```

### 2. 构建集群环境

#### 2.1 使用 ansible role 自动化搭建 swarm 集群

1. 修改配置文件 `imutils/IMConfig.py`, 设置 `## Node Managing Settings ##` 中定义的集群节点主机名称, ip, 预期的工作用户


2. 为上步的配置生成清单文件

   ```shell
    IocManager cluster --gen-inventory-files
   ```


3. 执行 playbook 以自动初始化集群环境, 根据需要设置 playbook 变量以选择执行其中的某些步骤
    ```shell
     # ansible_ssh_user: zhu  # ansible发起远程连接使用的账户, 通常为具有root权限的用户, 当设置为root时需配置ssh允许root用户密码登录
     # for_user: zhu  # 预期的工作用户, 若不存在需要创建
     # create_password: default  # 工作用户密码
     # skip_create_remote_user: false  # 是否跳过创建预期的工作用户
     # skip_set_up_ssh_connection: false  # 是否跳过设置ssh免密登录
     # skip_set_up_basic_environment: false  # 是否跳过设置基础运行环境
     # skip_set_up_cluster: false   # 是否跳过创建swarm集群
     # skip_install_docker_engine: false  # 创建swarm集群时, 是否跳过安装docker及相关依赖
     # skip_setup_docker_engine: false  # 创建swarm集群时, 是否跳过配置docker引擎
     # skip_setup_swarm_cluster: false  # 创建swarm集群时, 是否跳过自动初始化swarm集群
     # docker_swarm_interface: enp0s3  # 创建 swarm 集群时, 首个管理节点向外发布地址使用的网卡
     # docker_swarm_init_new_cluster: true  # 创建 swarm 集群时, 是否强制重新初始化swarm集群
     cd imtools/ansible
     ansible-playbook setup-cluster -i inventory/ -kK
    ```

4. 验证创建的集群环境

    ```shell
     # 运行以下命令显示集群信息, 若无报错则搭建成功
     IocManager cluster --ping 
     IocManager swarm --show-digest
     IocManager swarm --show-nodes --detail
    ```

#### 2.2 部署集群 NFS 服务

集群使用 NFS 来存储和共享系统数据及部分应用的程序数据.

由于 swarm 的编排调度对服务部署文件的插值均发生在管理端, 因此要求集群内所有节点的运行环境具有与管理节点相同的路径(在
`/home/user_name/docker/`目录下).

1. 配置 NFS server

    ```shell
     sudo vi /etc/exports
     # /home/zhu/NFS/IocDock-data 192.168.0.0/24(rw,sync,all_squash,no_subtree_check)
     # /home/zhu/NFS/registry-data 192.168.0.0/24(rw,sync,all_squash,no_subtree_check)
     sudo exportfs -a
    ```

2. 配置 NFS client

    ```shell
     # mount -t nfs ip-addr:/home/ubuntu/nfs-dir/IocDock-data dest-dir
     vi /etc/fstab
     # server_ip:/home/zhu/NFS/IocDock-data  /home/zhu/docker/IocDock-data  nfs  rw,_netdev,vers=4  0  0
     # server_ip:/home/zhu/NFS/registry-data  /home/zhu/docker/registry-data  nfs  rw,_netdev,vers=4  0  0
     sudo mount -a
    ```


2. 使用 playbook 实现集群主机批量自动化挂载 NFS 服务器(需要编辑 playbook 变量设置挂载细节)

    ```shell
     cd imtools/ansible
     ansible-playbook setup-nfs-mount -i inventory/ -K
    ```

### 3. 部署预置的集群服务

#### 3.1 部署 registry

1. `IMConfig.py` 中修改仓库域名

    ```shell
     REGISTRY_COMMON_NAME = f'registry.{PREFIX_STACK_NAME}'  # common name for registry https server
    ```

2. 生成仓库密钥对, 仓库密码文件

    ```shell
    cd imsrvs/registry/scripts
    ./make-certs.sh
    ./make-passwd.sh
   ```

3. 为需要运行 registry 的节点打上标签, 随后更新目录设置. registry 采用 NFS 共享后端, 因此需将所有 registry-data 目录挂载
   NFS

    ```shell
     # 管理节点初始需要运行一个 registry 实例以共享镜像仓库文件
     docker node update node_name --label-add registry=true 
     IocManager cluster --set-up-file-and-dir
     mount -t nfs nfs_ip:/home/nfs_user/NFS/registry-data /home/for_user/docker/registry-data
    ```

4. 将服务部署文件导出至共享目录, 并在每个节点运行证书设置脚本

    ```shell
     IocManager swarm --gen-builtin-services 
     cd /home/for_user/docker/IocDock-data/swarm/registry/scripts
     ./setup-certs.sh os-level
    ```

5. 启动服务, 编辑集群中的 /etc/hosts 以添加仓库域名的 dns 解析条目

    ```shell
     ./prepare-images.sh
     IocManager service registry --deploy
     sudo vi /etc/hosts
     # 192.168.1.50 registry.iasf
    ```

6. 准备镜像仓库, 并将集群 docker 登录至该仓库

    ```shell
     cd /home/for_user/docker/IocDock/imsrvs/registry/scripts
     ./prepare-images.sh
     cd /home/for_user/docker/IocDock/imtools/image-factory
     ./build-and-push-images.sh
     IocManager cluster --registry-login
    ```

#### 3.2 部署全局服务(alloy, cAdviosr, nodeExporter, iocLogServer, client)

1. 导出服务, 更新目录设置
    ```shell
     IocManager swarm --gen-builtin-services 
     IocManager cluster --set-up-file-and-dir
     IocManager swarm --deploy-global-services
     # alloy 服务地址: 192.168.1.50:12345
     # cAdvisor 服务地址: 192.168.1.50:8080
     # nodeExporter 服务地址: 192.168.1.50:9100
     # iocLogServer 服务地址: 192.168.1.50:7004
    ```

#### 3.3 部署本地服务(prometheus, loki, grafana)

1. 打上节点标签, 更新目录设置
    ```shell
     docker node update node_name --label-add prometheus=true 
     docker node update node_name --label-add loki=true 
     docker node update node_name --label-add grafana=true 
     IocManager cluster --set-up-file-and-dir
    ```

2. 部署
    ```shell
     IocManager service prometheus --deploy
     # prometheus 服务地址: 192.168.1.50:9090
     IocManager service loki --deploy
     # loki 服务地址: 192.168.1.50:3100
     IocManager service grafana --deploy
     # grafana 服务地址: 192.168.1.50:3000
    ```

#### 3.4 部署 alertManager

1. 设置 `IMConfig.py` 中 smtp 发件邮箱相关信息. 密码可以在其中设置密码或使用密码文件来实现

    ```yaml
     smtp_from: zhujunhua@mail.iasf.ac.cn
     smtp_smarthost: smtp.qiye.aliyun.com:465
     smtp_auth_username: zhujunhua@mail.iasf.ac.cn
     smtp_auth_password_file: /etc/alertmanager/smtp_password
     smtp_require_tls: false
    ```

2. 设置 `alertManager/config/alertManager-config.yaml` 以配置报警分级路由, 邮件接收分组等功能.


3. 打上节点标签, 更新目录设置, 部署
    ```shell
     IocManager swarm --gen-builtin-services
     docker node update node_name --label-add alertmanager=true 
     IocManager cluster --set-up-file-and-dir
     IocManager service alertManager --deploy
     # 192.168.1.50:9093
    ```

### 4. 部署 IOC 服务

#### 4.1 部署测试用 IOC 项目

1. 运行脚本生成测试 IOC 项目
    ```shell
     cd docker/IocDock
     ./make-test-project.sh make
    ```

2. 部署 IOC 项目至工作节点
    ```shell
     IocManager swarm --deploy-all-iocs
    ```

3. 查看正在运行的 IOC
    ```shell
    IocManager list -p
    IOC            Host    Description                               State    Status    DeployStatus            SnapshotConsistency    RuningConsistency
    worker_test_1  swarm   IOC that implements a ramper for test...  normal   exported  Running 9 seconds ago   consistent             consistent
    worker_test_2  swarm   IOC that implements a ramper for test...  normal   exported  Running 10 seconds ago  consistent             consistent
    worker_test_3  swarm   IOC that implements a ramper for test...  normal   exported  Running 10 seconds ago  consistent             consistent
    worker_test_4  swarm   IOC that implements a ramper for test...  normal   exported  Running 10 seconds ago  consistent             consistent
    worker_test_5  swarm   IOC that implements a ramper for test...  normal   exported  Running 10 seconds ago  consistent             consistent
    ```

4. 验证 IOC 的联通性. 至此已完成整个集群搭建. 访问各个服务地址以获取集群指标监控, 日志分析的全部运维管理功能.
    ```shell
       IocManager client caget ramper:worker_test_1
       IocManager client caget ramper:worker_test_1
       executing "docker exec 80ba9296482b ./caget ramper:worker_test_1".
       ramper:worker_test_1           6
    ```

#### 4.2 部署生产环境 IOC 项目

见后文 [IOC 项目的开发与部署](#a).

## 管理 IOC 项目与容器服务

## IOC 项目的开发与部署<a id="a"></a>

## old

##############################################################

#### 工作流程参考

当需要创建IOC项目并希望其正确运行在容器中时, 按如下顺序进行操作:

1. 新建IOC项目, 将所需的所有源文件添加至新建项目的"src/"目录.
2. 编辑IOC项目的配置文件设置参数. 如确定IOC项目将运行在哪个主机, 将使用的镜像及镜像内的可执行IOC; 设置DB部分load字段,
   确定IOC项目的db文件加载项; 确定IOC项目的其他配置等等.
3. 如要使用ASYN, STREAM或其他EPICS硬件设备通信插件时, 首先确保已选择镜像中的可执行IOC支持相关功能, 然后添加相关插件的配置模板,
   之后再进行配置.   
   *(ASYN, STREAM可直接添加已有的 "ASYN", "STREAM" 模板, 其他插件则需要添加并编辑 "RAW" 模板)*
4. 配置完成IOC项目后, 执行管理工具提供的命令生成IOC项目启动文件.
5. 生成项目启动文件后, 需要执行导出命令, 将IOC项目的启动文件导出至mount目录.
6. 妥当后, 若使用compose方式部署, 前往容器工作的虚拟机指定目录, 启动 docker compose 项目.
7. 若使用swarm模式部署, 则参考swarm部署文档, 执行管理工具提供的命令将IOC项目对应的docker服务部署.

### 使用帮助

#### 创建并设置IOC项目的配置文件

创建IOC项目, 通过命令设置配置或通过手动修改IOC项目配置文件的方式, 配置好IOC.    
参考如下列出的管理工具命令的大致使用方式, 详细使用方式见管理工具的命令行帮助.

1. 使用```create```命令, 创建IOC项目并进行简单配置. 如下为可执行的创建命令, 可同时使用多个选项:     
   ```IocManager create IOC [IOC2 IOC3 ...]``` 直接创建单个或多个IOC项目      
   ```IocManager create IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 创建时设置某些字段  
   ```IocManager create IOC [IOC2 IOC3 ...] -f xxx``` 导入已有配置文件创建   
   ```IocManager create IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave```
   指定使用的模块创建   
   ```IocManager create IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
   创建ASYN或STREAM模板并设置端口类型   
   ```IocManager create IOC [IOC2 IOC3 ...] --add-raw``` 创建时设置添加原始命令模板


2. 将IOC项目所需的源文件从指定目录添加至IOC项目的"src/"目录. 必要时可多次运行此命令.
   当前支持自动识别添加的文件名称后缀为 ```.db``` ```.proto``` ```.im```.    
   ```IocManager exec IOC [IOC2 IOC3 ...] --add-src-file --src-path xxx```
   > 也可直接手动将所有文件复制至"src/"目录. 指定```--add-src-file```且不指定```--src-path```,
   脚本默认将自动识别添加项目自身"src/"目录内的源文件.    
   (注: 此方式执行命令将刷新配置文件, 自动清除不存在于"src/"目录中的相关配置文件设置项)    
   ```IocManager exec IOC [IOC2 IOC3 ...] --add-src-file```


3. 创建IOC项目后如需要进一步配置IOC项目, 使用```set```命令. 如设置.db文件的加载项及宏替换, 指定协议文件,
   其他需要额外指定的启动命令, 等等. 如下选项可叠加设置:          
   ```IocManager set IOC [IOC2 IOC3 ...] -s xxx -o xxx=xxx``` 单独设置某些字段  
   ```IocManager set IOC [IOC2 IOC3 ...] -f xxx``` 导入配置文件覆盖设置    
   ```IocManager set IOC [IOC2 IOC3 ...] --caputlog/--status-ioc/--status-os/--autosave``` 设置使用的模块   
   ```IocManager set IOC [IOC2 IOC3 ...] --add-asyn/--add-stream [--port-type "tcp/ip"/"serial"]```
   设置ASYN或STREAM模板并设置端口类型   
   ```IocManager set IOC [IOC2 IOC3 ...] --add-raw``` 设置添加原始命令模板

> 也可直接打开IOC项目的ioc.ini文件手动编辑配置文件, 编辑时请注意文件格式.

#### 生成IOC项目的运行文件

对已配置完成的IOC项目, 需要生成IOC项目的运行文件及启动文件, 执行如下步骤.   
*执行此操作后, 工具将自动备份当前IOC项目的配置文件并更新IOC的项目状态属性用以进行项目周期管理.*

- 对指定的IOC项目生成运行文件及启动文件   
  ```IocManager exec IOC [IOC2 IOC3 ...] --gen-startup-file```

#### 导出IOC项目的运行文件

默认情况下, 创建生成的IOC项目存放于本地仓库目录"ioc-repository/". 在生成IOC运行文件之后, IOC项目就已经具备了运行所需的全部文件,
但为了管理方便, 还需将其导出至统一的mount目录下运行, 导出操作仅是执行文件目录的复制操作.

对已生成运行文件的IOC项目, 需要将其导出至mount目录, 以便可以使用容器平台运行, 执行如下步骤.

*执行此操作后, 工具将自动备份当前IOC项目的配置文件并更新IOC的项目状态属性用以进行项目周期管理.*

- 导出IOC项目运行文件至mount目录.    
  默认不覆盖, 即当IOC项目已存在于monut目录时, 只更新部分运行文件,
  IOC运行中一些插件模块记录产生的日志文件或配置文件将被保留.    
  也可以设置覆盖导入, 指定```--force-overwrite```,
  此时导出目录中的插件模块配置文件等将被初始化至项目刚生成运行文件时的状态.   
  ```IocManager exec IOC [IOC2 IOC3 ...] -e [--mount-path xxx] [--force-overwrite]```


- 工具提供了生成并导出IOC项目运行文件的快捷方法, 执行此操作将一次性调用生成和导出两个指令.    
  ```IocManager exec  IOC [IOC2 IOC3 ...] --generate-and-export [--mount-path xxx] [--force-overwrite]```

#### IOC项目的运行检查

- 对所有OC项目进行生命周期状态检查等相关检查, 工具将给出存在的问题并提供可能的操作办法.       
  ```IocManager exec --run-check```

#### 为导出的IOC项目生成配置文件以通过docker compose方式部署

- 为导出目录中存在的虚拟机文件夹生成docker compose文件. 需要指定iocLogserver所使用的base镜像. 指定```--hosts```
  来指定主机名称, 当需要为所有主机都执行生成操作时, 可将参数设置为```"allprojects"```.   
  ```IocManager exec --gen-compose-file --hosts allprojects [--mount-path xxx] --base-image xxx```

#### 为导出的IOC项目生成配置文件以通过docker swarm方式部署

- 为导出目录中swarm工作目录下的IOC项目生成swarm模式部署的docker compose文件. 指定```--ioc-list```
  来指定需要为哪些IOC项目执行操作, 当需要为所有IOC项目都执行生成操作时, 可将参数设置为```"alliocs"```.   
  ```IocManager exec --gen-swarm-file --ioc-list alliocs [--mount-path xxx]```

#### 运行部署的IOC项目

略. 详见compose部署文档或swarm部署文档.

#### IOC项目文件的备份及恢复

导出后运行的IOC项目可选择进行备份操作, 将当前本地仓库中所有IOC项目及其运行目录下的部分文件目录复制并打包为tgz文件.

备份时可选择两种模式  
```"src"```: 仅备份IOC项目源文件及配置文件    
```"all"```: 备份包括运行目录内插件模块运行时产生的文件在内的所有IOC文件

1. 备份时默认将自动进行IOC项目的运行前检查, 确保IOC项目是最新的且是正常可运行的, 运行前检查通过后方能继续备份.


2. 执行备份操作, 指定将备份文件的存储位置及备份模式, 工具将自动在目标位置生成带有时间戳的备份文件.    
   ```IocManager exec -b --backup-path xxx [--backup-mode "src"/"all"]```


3. 执行命令进行备份文件的恢复, 指定需要恢复的备份文件, 指定当IOC项目已存在时是否自动覆盖已存在的项目文件,
   将使备份文件内的IOC项目文件恢复至本地仓库目录   
   ```IocManager exec -r --backup-file xxx [--force-overwrite]```

#### 管理IOC项目

- 列出所有IOC项目. 若要列出时显示IOC项目的全部配置信息, 使用```-i```选项.   
  ```IocManager list [-i]```


- 按行列出IOC项目并显示状态信息, 使用```-r```选项.   
  ```IocManager list -r```


- 按行列出IOC项目并操作提示信息, 使用```-p```选项.   
  ```IocManager list -p```


- 根据条件筛选, 列出所有符合条件的IOC项目. 可以同时指定多个条件, 进行与逻辑筛选.     
  ```IocManager list condition [condition2 condition3 ...] [-i] [-r]```


- 通过项目名称进行模糊匹配, 列出IOC项目. 如下将筛选列出所有名称中包含"abc"的IOC项目.    
  ```IocManager list name=abc [-i] [-r]```


- 筛选所有具有指定字段设置的IOC项目. 如下将筛选并列出所有具有 "GHI" section 且其中"abc"字段属性值为"def"的IOC项目.   
  ```IocManager list abc=def -s ghi```


- 从给定的IOC列表中筛选IOC项目. 如下将筛选并列出x1, x2, x3三个IOC项目中具有 "GHI" section 且其中"abc"字段属性值为"def"
  的IOC项目.   
  ```IocManager list abc=def -s ghi -l x1 x2 x3```


- 嵌套筛选查找. 如下将从所有具有 "GHI" section 且其中"abc"字段的属性值为"def"的IOC项目中,
  筛选查找名称中包含"xyz"的IOC项目.   
  ```IocManager list abc=def -s ghi | xargsIocManager list name=xyz -l```


- 删除IOC项目. 注意删除时可指定的选项.   
  ```IocManager remove IOC [IOC2 IOC3 ...] [-r] [-f] ```


- 重命名IOC项目.   
  ```IocManager rename old-name new-name [-v] ```

#### 项目生命周期管理

IOC项目在执行创建、生成、导出操作后, 管理工具都会在"status[IOC]"字段更新当前状态.
此外, 在执行生成、导出操作后管理工具自动备份当前IOC项目的配置文件, 并更新"snapshot[IOC]"字段.
当管理工具检测到配置文件被修改, 导致与备份的配置文件不一致时, 将会修改"snapshot[IOC]"字段表明文件发生修改, 并给出相应提示.

*项目周期管理的目标是使所有IOC项目处于 "exported" 和 "logged" 状态,
表明IOC项目已导出至mount目录准备运行并且快照文件已是最新的.*

### IOC配置文件说明

可选配置将在下方用```*```号标注, 未标注则均为必须设置项, 需要进行配置才能使IOC项目正常运行.

部分配置项支持多行设置, 即每行可看作一个单独的设置项设置多个同类项.    
可在使用```IocManager create```或```IocManager set``` 命令指定属性时使用分号```;```间隔来代表多行设置,
也可在直接编辑配置文件时通过换行及缩进的方式来进行多行配置.

#### 通用配置设置

下方列出了每个创建的IOC项目都会具有的通用配置项, 参考说明进行配置.

<pre>
[IOC]       ---------------------------- 用以存储IOC的通用配置信息
name:       ---------------------------- IOC项目名称
host:       ---------------------------- IOC项目将在哪个主机中运行
image:       --------------------------- IOC项目将使用哪个镜像运行
bin:       ----------------------------- IOC将使用镜像中的哪个可执行IOC运行
*module:       ------------------------- IOC将自动安装的模块. 目前支持四个模块: autosave, caputlog, status-ioc, status-os
*description:       -------------------- IOC的描述信息
*status:       ------------------------- IOC项目的配置状态. "created"(IOC项目未生成运行文件) 或 "generated"(IOC项目已生成运行文件) 或 "exported"(IOC项目已导出)
*snapshot:       ----------------------- IOC配置文件的快照备份状态. ""(配置文件未备份) 或 "logged"(配置文件已备份且与备份文件一致) 或 "changed"(配置文件与备份文件不一致)
*is_exported:       -------------------- IOC项目的导出状态.

[SRC]       ---------------------------- 用以显示IOC项目中当前存在的源文件信息, 此字段自动更新，无需设置
*db_file:       ------------------------ 当前存在的db文件列表. 使用"--add-src-file"命令后将自动更新此列表
*protocol_file:       ------------------ 当前存在的协议文件列表.  
*others_file:       -------------------- 当前存在的其他以.im为后缀文件的列表.  

[DB]       ----------------------------- 用以存储IOC加载db文件的配置信息
load:       ---------------------------- 设置带宏替换的db文件加载项. 格式: *.db, A=abc, B=def    
            ---------------------------- 设置不使用宏替换的db文件加载项. 格式: *.db

[SETTING]       ------------------------ 用以存储IOC的附加配置信息
report_info:       --------------------- 设置IOC启动时是否报告当前IOC的PV信息等. "true" 或 "false"
caputlog_json:       ------------------- 设置caPutLog是否使用JSON格式. "true"(使用json格式) 或 "false"(使用文本格式)
*epics_env:       ---------------------- 设置EPICS环境变量. 格式: "xxx"="xxx"
                  ---------------------- 分行设置多个EPICS环境变量.
</pre>

```name[IOC]```: IOC名称, 决定IOC被分配的运行容器名称.
可以使用小写或下划线、数字(参考下方host字段). 应尽量避免与host字段相同. *要符合docker命名规范.*

```host[IOC]```: 主机名称, 指IOC将被分配至哪个主机中运行, 应与被分配主机的操作系统主机名称一致.
其中主机名称的命名方式必须符合正则表达式```"^[a-z0-9][a-z0-9_-]*$"```.

```image[IOC]```: 镜像名称, 指当前将使用的镜像, 不同的镜像版本可能支持不同的EPICS插件, 需要从镜像仓库中选择一个适合的镜像版本.

```bin[IOC]```: 镜像中可执行的IOC名称, 镜像中可能安装有不同IOC, 不同的IOC可能安装有不同的插件, 因此需要从镜像中正确选择一个可执行IOC.

```epics_env[SETTING]```: IOC shell使用的环境变量, 可以根据官方文档按需进行设置.

```load[DB]``` ```port_config[ASYN/STREAM]``` ```asyn_option[ASYN/STREAM]``` ```load[ASYN]```
```epics_env[SETTING]``` ```cmd_*[RAW]``` ```file_copy[RAW]```支持多行设置.

#### 特殊配置设置

以下配置均为模板, 实际使用中根据需求调整设置. 对部分可以有重复多项的设置(如load, cmd, file_copy, port_config等)
可以按前述, 用分号或换行缩进的方式进行设置.

- 基于网络的ASYN配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: tcp/ip
port_config: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
load: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于串口的ASYN配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中

<pre>
[ASYN]
port_type: serial
port_config: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option: asynSetOption("L0", -1, "baud", "9600")
  asynSetOption("L0", -1, "bits", "8")
  asynSetOption("L0", -1, "parity", "none")
  asynSetOption("L0", -1, "stop", "1")
  asynSetOption("L0", -1, "clocal", "Y")
  asynSetOption("L0", -1, "crtscts", "Y")
load: dbLoadRecords("db/asynRecord.db","P=xxx,R=:asyn,PORT=xxx,ADDR=xxx,IMAX=xxx,OMAX=xxx")
</pre>

- 基于网络的StreamDevice配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中. 多个协议文件以逗号分隔.

<pre>
[STREAM]
port_type: tcp/ip
port_config: drvAsynIPPortConfigure("L0","192.168.0.23:4001",0,0,0)
protocol_file: x.proto, xx.proto
</pre>

- 基于串口的StreamDevice配置模板, 设置项将作为文本直接添加至IOC启动脚本文件中

<pre>
[STREAM]
port_type: serial
port_config: drvAsynSerialPortConfigure("L0","/dev/tty.PL2303-000013FA",0,0,0)
asyn_option: asynSetOption("L0", -1, "baud", "9600")
  asynSetOption("L0", -1, "bits", "8")
  asynSetOption("L0", -1, "parity", "none")
  asynSetOption("L0", -1, "stop", "1")
  asynSetOption("L0", -1, "clocal", "Y")
  asynSetOption("L0", -1, "crtscts", "Y")
protocol_file: xxx.proto
</pre>

- 开放的自定义操作接口, 主要执行两点操作

1. IOC启动文件原始命令设置接口, 支持st.cmd文件命令的自定义设置
2. 系统文件的复制操作接口, 用于执行生成启动文件时的复制操作

*在执行IOC项目运行文件的生成时, 会将此处设置的原始命令直接添加至st.cmd脚本, 将文件从本地计算机的某位置复制到IOC项目的运行文件夹中.
例如在使用ASYN时会将"asynRecord.db"从工具的模板仓库复制至IOC项目目录; 使用STREAM时会将协议文件复制至IOC项目目录等.
使用其他未提供配置模板的EPICS插件时, 若需要添加相关IOC启动命令或进行文件复制处理时, 设置此字段.*

> 注: 使用file_copy字段的格式: "path to src file" : "path to dest file" [: "mode"].   
"mode"不设置时默认为"r", 表示只读复制. 可设置目的文件的权限为"rwx"的任意组合, 同Linux操作系统.

<pre>
[RAW]
*cmd_before_dbload: 
*cmd_at_dbload: 
*cmd_after_iocinit: 
*file_copy: 
</pre>

### 项目目录结构说明

<pre>
├── auto-test-for-IocManager.sh*       --------------------------------- 管理工具的测试脚本
├── auto-update.sh*       ---------------------------------------------- 管理工具的升级脚本
├── docs/       -------------------------------------------------------- 文档目录
├── imtools/       ----------------------------------------------------- 存放其他脚本及程序文件的目录
│   ├── command-completion/       -------------------------------------- 命令补全
│   │   ├── command-completion.sh       -------------------------------- 命令补全脚本
│   │   ├── install-command-completion.sh       ------------------------ 命令补全功能的安装脚本
│   ├── docker-manager/       ------------------------------------------ 配置操作系统docker环境的工具目录
│   │   ├── certs/       ----------------------------------------------- 存放证书生成脚本及TLS证书
│   │   ├── compose-agent.yaml       ----------------------------------- portainer agent主机使用的docker compose文件
│   │   ├── compose.yaml       ----------------------------------------- docker manager主机使用的docker compose文件
│   │   ├── set-docker-environment.sh       ---------------------------- docker运行所需环境的设置脚本
│   │   ├── start-compose-agent.sh       ------------------------------- 启动portainer agent的脚本
│   │   └── start-docker-manager.sh       ------------------------------ 启动docker manager的脚本
│   ├── IMFuncsAndConst.py       --------------------------------------- 管理工具的公共函数及公共变量
│   ├── IocClass.py       ---------------------------------------------- 管理工具的IOC类定义文件
│   ├── ioc-snapshot/       -------------------------------------------- IOC项目配置文件快照目录
│   ├── SwarmClass.py       -------------------------------------------- 管理工具的swarm类定义文件
│   └── template/       ------------------------------------------------ 模板文件目录
├── IocManager.py       ------------------------------------------------ 管理工具执行脚本
├── ioc-repository/       ---------------------------------------------- 管理工具当前的IOC仓库目录
└── make-test-project.sh       ----------------------------------------- 生成IOC项目测试用例的脚本
</pre>


更新日志及功能说明
------------------------------------------------------------------------

beta v0.5.2   
======= 2024/10/10 =======

1. IOC项目生命周期管理优化
2. 其他优化
3. 管理工具调用优化











