# Image Repository

本项目可编译含有IOC可执行文件的容器镜像. 

### 一般使用帮助

#### 编译最新版本镜像

在需要编译新版本时, 按如下操作.
> 1. 执行 ```git remote update```, ```git pull origin master``` 更新并拉取git项目的最新代码.
> 2. 各安装包均已压缩存储到git项目中, 以管理员身份运行 ```auto-make-images.sh```即可.

### 当前版本镜像说明

#### base镜像(base:beta-0.2.2)

- 基于轻量化ubuntu
- EPICS base-7.0.8.1
- 容器内工作目录/opt/EPICS
- 参考项目内README文件进行镜像构建后的测试

#### ioc-exec镜像(ioc-exec:beta-0.2.2)

- 基于镜像base:beta-0.2.2
- 已安装的可执行IOC: ST-IOC
- 当前版本支持的EPICS插件(ST-IOC): "seq" "asyn" "autosave" "caPutLog" "iocStats" "StreamDevice" "modbus" "s7nodave" "BACnet"
- 参考项目内README文件进行镜像构建后的测试
