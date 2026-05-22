################# 系统配置 ##################################

# 集群栈名称(命名空间)
PREFIX_STACK_NAME = "iasf"

# 系统共享目录NFS挂载配置
MOUNT_DIR_NFS_MOUNT_SRC = "192.168.1.60:/NFS/IocDock-data"

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
    "managerA": "192.168.1.60",
    "managerB": "192.168.1.61",
    "managerC": "192.168.1.62",
}
# swarm集群工作节点
CLUSTER_WORKER_NODES = {
    # "hostname": "ip address",
    "workerA": "192.168.1.63",
    "workerB": "192.168.1.64",
}
# 其余服务器节点
DEFAULT_NODES = {
    # "hostname": "ip address",
    "nfs": "192.168.1.60"
}
# swarm集群adververtiser IP(SWARM_ADDVERTISER_IP或SWARM_ADDVERTISER_INTERFACE填写一个即可)
SWARM_ADDVERTISER_IP = ""
SWARM_ADDVERTISER_INTERFACE = "eth1"
# Ansible远程登录用户(需要具有root权限)
ANSIBLE_SSH_USER = "ubuntu"
# Ansible创建的iocdock用户密码
ANSIBLE_CREATE_PASSWORD = ""

################# Registry 配置 ############################

# registry数据共享目录挂载配置
REGISTRY_NFS_MOUNT_SRC = "192.168.1.60:/NFS/registry-data"
REGISTRY_MASTER_IP = "192.168.1.60"
REGISTRY_LOGIN_USERNAME = ""
REGISTRY_LOGIN_PASSWORD = ""

################# AlertManager 配置 ########################

# AlertManager集群master节点IP
ALERT_MANAGER_MASTER_IP = "192.168.1.60"

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
