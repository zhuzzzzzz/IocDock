## Image Factory

编译并上传含有 EPICS base 及 IOC 运行环境的容器镜像. 

### 使用帮助

#### 构建并上传镜像

```shell
# 执行脚本构建和上传预先定义的默认镜像
./build-and-push-default-images.sh
```

### 镜像版本说明

#### 版本号格式

过去版本将所有 EPICS 插件全部安装在同一个 IOC 镜像中，然而实际生产环境中 IOC 往往仅需要其中的一部分, 为了尽可能减小分发的运行镜像大小，我们将通用模块提取出来，对于其他依赖特定模块的 IOC 镜像再进行单独构建. 在运行 IOC 数量多且 IOC 类别多的情况下, 这样做可以显著减小镜像大小对宿主机的磁盘空间占用. 因此需要对镜像进行分类管理，在此对镜像版本进行说明。

IOC 镜像的版本号格式为: "ioc-exec:<大版本号>-<小版本号>-<EPICS插件版本号>"   

其中 "<大版本号>" 为当前镜像大版本号, 用于标识重大版本更新, "<小版本号>"用于表示小功能更新, "<EPICS插件版本号>"用于标识当前镜像安装有哪些可供使用的EPICS插件.

为保证格式统一, base 镜像的版本号采用类似格式: "base:<大版本号>-<中版本号>-<小版本号>", 但每一位没有明确的含义, 仅依序表示版本的不同.

#### base 镜像各版本镜像说明

##### 通用说明

- 基于轻量化 ubuntu
- 容器内安装路径 /opt/EPICS/base-*/

##### base:1.0.0

- 包含构建好的 EPICS base-7.0.8.1 及相关运行依赖环境

#### IOC 镜像各版本镜像说明

##### 通用说明

- 已安装的可执行 IOC : "ST-IOC"
- 容器内安装路径 /opt/EPICS/IOC/

##### 关于 seq 插件

默认安装的 "seq" 插件仅编译 SNL 状态机文件实例 hello, 在 IOC shell 中运行 ```seq hello``` 启动.   
若要编译并使用自定义的 SNL 状态机文件, 请将状态机文件拷贝至 /IOC/ioc-tools/ 目录下在进行镜像构建, 并在构建 IOC 镜像时指定构建 seq 

##### ioc-exec:1.0.0

- 基于 base 镜像 base:1.0.0
- 支持默认的通用 EPICS 插件: "seq" "autosave" "caPutLog" "iocStats" 
- 适用不需要任何硬件通信插件的软 IOC

##### ioc-exec:1.0.1

- 基于 base 镜像 base:1.0.0
- 支持 EPICS 插件: "seq" "asyn" "autosave" "caPutLog" "iocStats" "StreamDevice" "modbus" 
- 适用需要基于 asyn, StreamDevice, modbus 插件进行通信的 IOC

##### ioc-exec:1.0.2

- 基于 base 镜像 base:1.0.0
- 支持 EPICS 插件: "seq" "asyn" "autosave" "caPutLog" "iocStats" "s7nodave" 
- 适用需要基于 s7nodave 插件进行通信的 IOC

##### ioc-exec:1.0.3

- 基于 base 镜像 base:1.0.0
- 支持 EPICS 插件: "seq" "asyn" "autosave" "caPutLog" "iocStats" "BACnet" 
- 适用需要基于 BACnet 插件进行通信的 IOC