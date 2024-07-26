# 基于容器架构的虚拟机集群IOC项目部署文档

阅读本文档，以了解操作系统运行环境如何进行配置，以及如何运行启动IOC项目以及容器管理平台。

当前控制系统关于IOC部署运行的架构中，大部分IOC是运行在由两台VMware主机形成的虚拟机集群中。
IOC运行在容器之中，一个容器装载一个IOC运行，一台虚拟机主机可以运行多个容器。
本文档是关于如何在这个虚拟机集群中部署虚拟机操作系统，完成IOC项目部署的前置环境，以配合自行开发的IOC项目管理工具使用。

下方首先介绍关于各个部分的概念解释。当需要针对哪个部分单独配置时，参见下方每个部分单独给出的流程步骤进行配置。

### 名词解释

### docker-manager

docker-manager，是指在虚拟机管理系统中运行容器管理平台的centos7虚拟机，简称管理主机。管理主机不参与容器的IOC运行，管理主机上运行有一个Portainer
Server，
其与所有工作主机的Portainer agent进行通信以实现管理功能。此外，在此主机之中还运行一个registry镜像仓库，
其中存储了架构中其他主机将使用的容器镜像。   

访问 https://(docker-manager ip):9443 以进入容器管理平台界面   
访问 https://(docker-manager ip)/v2/_catalog 以查看当前镜像仓库中有哪些镜像

### worker-standard

worker-standard，是指在虚拟机管理系统中的centos7虚拟机，简称工作机模板。其中已配置好公共的软件环境，作为标准模板，可以供其他工作机直接克隆使用。

### workers

workers，是指在将要虚拟机管理系统中工作的centos7虚拟机，由工作机模板按需克隆而来。当需要添加新的虚拟机主机运行IOC时，克隆此模板，
并按下方给出的配置流程进行配置操作，以创建并启动该主机应运行的IOC项目。

__当前所有虚拟机都运行在同一局域网，互相之间可通过二层交换机进行访问。
当添加虚拟机时，需注意其VMware的网络VLAN配置要与交换机的VLAN配置对应__

### IOC部署管理工具

[git项目地址](http://120.25.165.98/zhujunhua/repository-ioc)   
自行开发的Python脚本工具，包含容器镜像的生成脚本，系统环境的配置脚本等。实现的功能有：IOC项目的创建、管理，IOC运行文件自动生成，IOC项目的备份恢复等功能。
具体请参考工具内的使用文档。

## docker-manager

#### 网络环境

- ip:192.168.20.247
- gateway:192.168.20.254  
  ```nmtui```设置网卡ens224

#### centos系统环境

- 启动sshd服务   
  ```systemctl enable sshd```   
  ```systemctl start sshd```
- 关闭防火墙   
  ```systemctl disable firewalld```   
  ```systemctl stop firewalld```
- 执行yum更新   
  ```yum update```
- 将default用户添加至sudo列表
- 将default用户添加至docker组
- 主机名称设置(docker-manager)
- 时区设置, 并设置从网络自动更新时间   
  ```timedatectl set-timezone Asia/Shanghai```
- NFS设置   
  ```yum install nfs-utils```   
  编辑链接/etc/rc.local设置开机启动mount, 注意需要赋予被链接文件的执行权限, 否则无法实现开机mount   
  ```mount -t nfs -o vers=3 192.168.20.221:/NFS_NIS_VOL01/home/ctrl01/Desktop/Docker /home/default/Docker```

#### python环境

- 安装必要的python包   
  ```pip3 install pyyaml```

#### docker运行环境

- 安装最新版本docker并设置docker服务开机自启动   
  ```systemctl enable docker```   
  ```systemctl enable containerd```

#### 服务配置及启动

- 克隆IOC管理工具至Docker/目录下   
  ```git clone http://120.25.165.98/zhujunhua/repository-ioc.git```
- 生成本地portainer_data卷   
  ```docker volume create portainer_data```
- 切换至/home/default/Docker/repository-ioc/imtools/docker-manager/目录下，执行初始化运行脚本   
  ```./set-docker-environment.sh manager```
- 启动docker-manager的compose项目   
  ```./start-docker-manager.sh```
- 给本地镜像打标签并上传至本地registry服务器    
  ```docker tag base:beta-0.1.1 image.dals/base:beta-0.1.1```   
  ```docker push image.dals/base:beta-0.1.1```
- 登录192.168.20.253:9443配置portainer service

## worker-standard

#### 网络环境

- ip:192.168.20.100
- gateway:192.168.20.254   
  ```nmtui```设置网卡ens224

#### centos系统环境

- 启动sshd服务   
  ```systemctl enable sshd```   
  ```systemctl start sshd```
- 关闭防火墙   
  ```systemctl disable firewalld```   
  ```systemctl stop firewalld```
- 执行yum更新   
  ```yum update```
- 将default用户添加至sudo列表
- 将default用户添加至docker组
- 主机名称设置(docker-standard)
- 时区设置   
  ```timedatectl set-timezone Asia/Shanghai```
- 设置NTP   
  ```yum install ntp```   
  ```sudo systemctl start ntpd```   
  ```sudo systemctl enable ntpd```
- NFS设置    
  ```yum install nfs-utils```   
  编辑链接/etc/rc.local设置开机启动mount, 注意需要赋予被链接文件的执行权限, 否则无法实现开机mount   
  ```mount -t nfs -o vers=3 192.168.20.221:/NFS_NIS_VOL01/home/ctrl01/Desktop/Docker/ioc-for-docker/$(hostname) /home/default/Docker/IOC```   
  ```mount -t nfs -o vers=3 192.168.20.221:/NFS_NIS_VOL01/home/ctrl01/Desktop/Docker/repository-ioc/imtools/docker-manager /home/default/Docker/docker-manager```

#### docker运行环境

- 安装最新版本docker并设置docker服务开机自启动   
  ```systemctl enable docker```   
  ```systemctl enable containerd```

## workers

#### 通过worker-standard模板虚拟机克隆虚拟机

#### 网络环境

- ip:192.168.20.(101-130)(131-133)
- gateway:192.168.20.254   
  ```nmtui```设置网卡ens224

#### centos系统环境

- 设置主机名称, 主机名称需要与IOC项目文件的配置完全一致! 设置完成后需要重启以更新NFS mount信息!

#### 服务配置及启动

- 切换至/home/default/Docker/docker-manager/目录下，执行初始化运行脚本   
  ```./set-docker-environment.sh```
- 启动compose-agent的compose项目   
  ```./start-compose-agent.sh```
- 登录portainer服务器192.168.20.247:9443添加portainer agent

#### 启动IOC服务

- 配置好IOC项目的配置文件, 按文档生成IOC运行文件的mount目录, 具体方式见IOC部署管理工具文档   
- 对每台工作机分别操作，切换至/home/default/Docker/IOC/目录下，启动IOC项目的compose项目   
  ```docker compose up -d```
