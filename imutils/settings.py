################# 系统配置 ##################################

# 集群栈名称(命名空间)
PREFIX_STACK_NAME = "iasf"

# NFS挂载配置
MOUNT_DIR_NFS_MOUNT_SRC = "192.168.1.50:/home/zhu/NFS/IocDock-data"
REGISTRY_NFS_MOUNT_SRC = "192.168.1.50:/home/zhu/NFS/registry-data"

################# 部署配置 ##################################

# IOC默认安装的模块("autosave" "caputlog" "status-ioc" "status-os")
DEFAULT_MODULES = "autosave, caputlog"

# IOC容器CPU限制
RESOURCE_IOC_CPU_LIMIT = "1"
# IOC容器内存限制
RESOURCE_IOC_MEMORY_LIMIT = "1G"

################# Ansible 配置 #############################

# swarm集群管理节点
CLUSTER_MANAGER_NODES = {
    # "hostname": "ip address",
    "ubuntu-server": "192.168.1.50",
    "ubuntu-new": "192.168.1.51",
    "manager0": "192.168.1.52",
    "manager1": "192.168.1.53",
}
# swarm集群工作节点
CLUSTER_WORKER_NODES = {
    # "hostname": "ip address",
    "worker0": "192.168.1.54",
    "worker1": "192.168.1.55",
}
# 其余服务器节点
DEFAULT_NODES = {
    # "hostname": "ip address",
    "nfs": "192.168.1.50"
}
# swarm集群adververtiser IP(SWARM_ADDVERTISER_IP或SWARM_ADDVERTISER_INTERFACE填写一个即可)
SWARM_ADDVERTISER_IP = ""
SWARM_ADDVERTISER_INTERFACE = "enp3s0"
# Ansible远程登录用户(需要具有root权限)
ANSIBLE_SSH_USER = "root"
# Ansible创建用户
ANSIBLE_FOR_USER = "zhu"
# Ansible创建用户密码
ANSIBLE_CREATE_PASSWORD = ""

################# AlertManager 配置 ########################

# AlertManager集群master节点IP
ALERT_MANAGER_MASTER_IP = "192.168.1.50"

# AlertManager邮箱服务器地址
ALERT_MANAGER_SMTP_SMART_HOST = "smtp.qiye.aliyun.com:465"
# AlertManager邮箱服务器认证用户
ALERT_MANAGER_SMTP_AUTH_USERNAME = "zhujunhua@mail.iasf.ac.cn"
# AlertManager邮箱服务器认证用户密钥
ALERT_MANAGER_SMTP_AUTH_PASSWORD = None
# AlertManager发件邮箱
ALERT_MANAGER_SMTP_EMAIL_SEND_ADDRESS = "zhujunhua@mail.iasf.ac.cn"
# AlertManager收件邮箱
ALERT_MANAGER_RECEIVE_EMAIL_LIST = ["1728831951@qq.com"]

# 用以接收AlertManager所有告警信息的webhook
ALERT_MANAGER_DEFAULT_WEBHOOK_RECEIVER = "http://192.168.20.170:8081/webhook/prometheus"
# 用以接收AlertManager INFO程度告警信息的webhook
ALERT_MANAGER_INFO_WEBHOOK_RECEIVER = "http://192.168.1.51:8000/alerts"
