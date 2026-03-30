#### 使用 ansible role 实现服务器集群自动初始化

1. 修改配置文件 `imutils/IMConfig.py` **或创建配置文件 `imutils/IMConfigCustom.py`**.    
设置 `## Node Managing Settings ##` 部分, 定义集群节点主机名称, ip, 服务器上生效的管理用户.


2. 生成主机清单文件

   ```shell
    $ IocManager cluster --gen-inventory-files
   
    # 生成的清单文件可作为执行其他ansible操作的主机清单文件
    $ ansible all -m ping -i inventory/ 
    # 或执行需要root权限的操作
    $ ansible all -m ping -i inventory/ -bK
   ```


3. 执行 `setup-cluster.yaml` playbook 以自动初始化集群环境, 设置 playbook 变量以执行其中特定某些步骤
    ```shell
     # ansible_ssh_user: zhu  # ansible发起远程连接的目标用户, 通常为具有root权限的用户, 当设置为root用户时远端主机需配置ssh允许密码登录root用户
     # for_user: zhu  # 预期生效的管理用户, 若不存在则创建该用户
     # create_password: default  # 管理用户密码
     # skip_create_remote_user: false  # 是否跳过创建预期生效的管理用户
     # skip_set_up_ssh_connection: false  # 是否跳过设置ssh免密登录
     # skip_set_up_basic_environment: false  # 是否跳过设置基础运行环境
     # skip_set_up_swarm: false   # 是否跳过创建swarm集群
     # skip_install_docker_engine: false  # 创建swarm集群时, 是否跳过安装docker及相关依赖
     # skip_setup_docker_engine: false  # 创建swarm集群时, 是否跳过配置docker引擎
     # skip_setup_swarm_cluster: false  # 创建swarm集群时, 是否跳过自动初始化swarm集群
     # docker_swarm_interface: enp0s3  # 创建 swarm 集群时, 首个管理节点向外发布地址使用的网卡
     # docker_swarm_init_new_cluster: true  # 创建 swarm 集群时, 是否强制重新初始化swarm集群
     $ cd imtools/ansible
     $ ansible-playbook setup-cluster -i inventory/ -kK
     $ reboot
    ```

4. 验证创建的集群环境

    ```shell
     # 运行以下命令显示集群信息, 若无报错则搭建成功
     $ IocManager cluster --ping 
     $ IocManager swarm --show-digest
     $ IocManager swarm --show-nodes --detail
    ```

#### 基于 ansible role 管理服务器集群

1. 修改配置文件 `imutils/IMConfig.py` **或创建配置文件 `imutils/IMConfigCustom.py`**.    
设置 `## Node Managing Settings ##` 部分, 定义集群节点主机名称, ip, 服务器上生效的管理用户.


2. 生成主机清单文件

   ```shell
    $ IocManager cluster --gen-inventory-files
   
    # 生成的清单文件可作为执行其他ansible操作的主机清单文件
    $ ansible all -m ping -i inventory/ 
    # 或执行需要root权限的操作
    $ ansible all -m ping -i inventory/ -bK
   ```

3. 使用集群管理命令

    ```shell
    # 仅创建集群主机的生效用户, 并设置用户权限
    $ IocManager cluster --create-remote-user

    # 为集群服务器创建免密ssh连接
    $ IocManager cluster --set-up-ssh-connection

    # 为集群服务器设置基础运行环境
    $ IocManager cluster --set-up-basic-environment

    # 构建swarm集群
    $ IocManager cluster --set-up-swarm

    # 按顺序执行以上四步
    $ IocManager cluster --set-up-cluster
    ```
